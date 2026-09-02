import { TiktokDL } from './lib/ttapi.js'
import { CheckFacebookCookie, ReelsUpload } from './lib/browserHandler.js'
import dotenv from 'dotenv'
import TeleBot from 'telebot'
import axios from 'axios'
import ProgressBar from 'progress'
import chalk from 'chalk'
import path from 'path'
import fs from 'fs'

dotenv.config()

const BOT_TOKEN = process.env.BOT_TOKEN
const MAX_COOKIE_FILE_SIZE = 2 * 1024 * 1024
const ACCOUNTS_ROOT = path.resolve('accounts')
const DOWNLOAD_ROOT = path.resolve('download')
const ALLOWED_TELEGRAM_IDS = new Set(
  (process.env.ALLOWED_TELEGRAM_IDS || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
)
const userStats = new Map()
const activeVideoIds = new Set()

if (!BOT_TOKEN || BOT_TOKEN === 'your_bot_token_here') {
  console.error('BOT_TOKEN is missing. Please edit .env and set BOT_TOKEN=your_real_telegram_bot_token')
  process.exit(1)
}

const bot = new TeleBot({ token: BOT_TOKEN })

function isAllowedUser(msg) {
  return ALLOWED_TELEGRAM_IDS.size === 0 || ALLOWED_TELEGRAM_IDS.has(String(msg.from.id))
}

function rejectUnauthorized(msg) {
  if (isAllowedUser(msg)) return false
  bot.sendMessage(msg.chat.id, `Bạn không có quyền dùng bot này. Telegram ID của bạn: ${msg.from.id}`)
  return true
}

function sanitizeAccountName(fileName) {
  const baseName = path.basename(fileName, path.extname(fileName))
  const normalized = baseName
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)

  return normalized || `facebook_${Date.now()}`
}

function getUserAccountDir(userId) {
  return path.join(ACCOUNTS_ROOT, String(userId))
}

function getAccountPath(userId, accountName) {
  return path.join(getUserAccountDir(userId), `${accountName}.json`)
}

function getSelectionPath(userId) {
  return path.join(getUserAccountDir(userId), '_selected.json')
}

async function listAccounts(userId) {
  const userDir = getUserAccountDir(userId)
  try {
    const entries = await fs.promises.readdir(userDir, { withFileTypes: true })
    return entries
      .filter((entry) => entry.isFile() && entry.name.endsWith('.json') && entry.name !== '_selected.json')
      .map((entry) => path.basename(entry.name, '.json'))
      .sort()
  } catch (error) {
    if (error.code === 'ENOENT') return []
    throw error
  }
}

async function selectAccount(userId, accountName) {
  const accountPath = getAccountPath(userId, accountName)
  await fs.promises.access(accountPath)
  await fs.promises.writeFile(
    getSelectionPath(userId),
    JSON.stringify({ accountName }, null, 2),
    'utf8'
  )
}

async function getSelectedAccount(userId) {
  try {
    const selection = JSON.parse(await fs.promises.readFile(getSelectionPath(userId), 'utf8'))
    const accountName = sanitizeAccountName(selection.accountName || '')
    const cookiePath = getAccountPath(userId, accountName)
    await fs.promises.access(cookiePath)
    return { accountName, cookiePath }
  } catch (error) {
    return null
  }
}

function validateFacebookCookies(data) {
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error('File JSON phải là một mảng cookie và không được để trống.')
  }

  const validCookies = data.every((cookie) => (
    cookie &&
    typeof cookie === 'object' &&
    typeof cookie.name === 'string' &&
    typeof cookie.value === 'string'
  ))

  if (!validCookies) {
    throw new Error('Cookie không đúng định dạng. Mỗi cookie cần có name và value.')
  }

  const cookieNames = new Set(data.map((cookie) => cookie.name))
  if (!cookieNames.has('c_user') || !cookieNames.has('xs')) {
    throw new Error('Không tìm thấy cookie Facebook c_user và xs. Hãy xuất lại cookie khi đang đăng nhập Facebook.')
  }
}

async function inspectFacebookCookieFile(cookiePath) {
  const cookies = JSON.parse(await fs.promises.readFile(cookiePath, 'utf8'))
  if (!Array.isArray(cookies) || cookies.length === 0) {
    return {
      ok: false,
      message: 'Cookie file is empty or not a JSON array.'
    }
  }

  const nowSeconds = Date.now() / 1000
  const cookieNames = new Set(cookies.map((cookie) => cookie.name))
  const importantNames = ['c_user', 'xs', 'fr', 'datr', 'sb']
  const important = importantNames.map((name) => {
    const cookie = cookies.find((item) => item.name === name)
    const expires = cookie?.expires || cookie?.expirationDate || cookie?.expiry
    return {
      name,
      exists: Boolean(cookie),
      expired: Boolean(expires && expires > 0 && expires <= nowSeconds),
      expiresAt: expires && expires > 0 ? new Date(expires * 1000).toISOString() : 'session/no-expiry'
    }
  })

  const missing = important
    .filter((cookie) => ['c_user', 'xs'].includes(cookie.name) && !cookie.exists)
    .map((cookie) => cookie.name)
  const expired = important
    .filter((cookie) => cookie.expired)
    .map((cookie) => cookie.name)

  const lines = [
    `Cookie count: ${cookies.length}`,
    `Has c_user: ${cookieNames.has('c_user') ? 'yes' : 'no'}`,
    `Has xs: ${cookieNames.has('xs') ? 'yes' : 'no'}`,
    ...important
      .filter((cookie) => cookie.exists)
      .map((cookie) => `${cookie.name} expires: ${cookie.expiresAt}`)
  ]

  if (missing.length > 0) {
    return {
      ok: false,
      message: `Missing required cookie(s): ${missing.join(', ')}\n${lines.join('\n')}`
    }
  }

  if (expired.length > 0) {
    return {
      ok: false,
      message: `Expired cookie(s): ${expired.join(', ')}\n${lines.join('\n')}`
    }
  }

  return {
    ok: true,
    message: `Cookie file looks structurally OK. Facebook can still reject it server-side if the session was logged out, checkpointed, or used from a different IP/device.\n${lines.join('\n')}`
  }
}

async function listStoredVideos() {
  try {
    const entries = await fs.promises.readdir(DOWNLOAD_ROOT, { withFileTypes: true })
    const videos = await Promise.all(
      entries
        .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.mp4'))
        .map(async (entry) => {
          const filePath = path.join(DOWNLOAD_ROOT, entry.name)
          const stats = await fs.promises.stat(filePath)
          return {
            id: path.basename(entry.name, path.extname(entry.name)),
            size: stats.size,
            modifiedAt: stats.mtimeMs
          }
        })
    )

    return videos.sort((a, b) => b.modifiedAt - a.modifiedAt)
  } catch (error) {
    if (error.code === 'ENOENT') return []
    throw error
  }
}

function isSafeVideoId(videoId) {
  return /^[a-zA-Z0-9_-]{1,100}$/.test(videoId)
}

async function deleteStoredVideo(videoId) {
  if (!isSafeVideoId(videoId)) {
    throw new Error('ID video không hợp lệ.')
  }

  if (activeVideoIds.has(videoId)) {
    return { deleted: false, active: true }
  }

  const videoPath = path.join(DOWNLOAD_ROOT, `${videoId}.mp4`)
  const metadataPath = path.join(DOWNLOAD_ROOT, `${videoId}_metadata.json`)

  try {
    await fs.promises.unlink(videoPath)
  } catch (error) {
    if (error.code === 'ENOENT') return { deleted: false, active: false }
    throw error
  }

  await fs.promises.unlink(metadataPath).catch((error) => {
    if (error.code !== 'ENOENT') throw error
  })
  return { deleted: true, active: false }
}

function updateUserStats(userId) {
  const today = new Date().toDateString()
  if (!userStats.has(userId)) {
    userStats.set(userId, { date: today, count: 1 })
    return
  }

  const stats = userStats.get(userId)
  if (stats.date !== today) {
    stats.date = today
    stats.count = 1
  } else {
    stats.count++
  }
}

function pickVideo(videos) {
  if (!videos || videos.length === 0) return null
  const selectedVideo = videos[0]
  return typeof selectedVideo === 'string' ? { url: selectedVideo } : selectedVideo
}

async function downloadVideo(url, outputPath) {
  const { data, headers } = await axios({
    url,
    method: 'GET',
    responseType: 'stream'
  })

  if (!fs.existsSync('download')) fs.mkdirSync('download')

  const totalLength = Number(headers['content-length']) || 0
  const progressBar = new ProgressBar(`[ ${chalk.hex('#ffff1c')('Downloading')} ] [${chalk.hex('#6be585')(':bar')}] :percent in :elapseds`, {
    width: 40,
    complete: '<',
    incomplete: '.',
    renderThrottle: 1,
    total: totalLength || 1
  })

  data.on('data', (chunk) => {
    if (totalLength) progressBar.tick(chunk.length)
  })

  const writer = fs.createWriteStream(outputPath)
  data.pipe(writer)

  await new Promise((resolve, reject) => {
    writer.on('finish', resolve)
    writer.on('error', reject)
    data.on('error', reject)
  })

  if (!totalLength) progressBar.tick(1)
}

async function handleTikTokUrl(msg, url) {
  const chatId = msg.chat.id
  const userId = msg.from.id

  try {
    if (rejectUnauthorized(msg)) return

    const selectedAccount = await getSelectedAccount(userId)
    if (!selectedAccount) {
      return bot.sendMessage(chatId, 'Bạn chưa chọn tài khoản Facebook. Hãy gửi file cookie JSON vào bot trước.')
    }

    await bot.sendMessage(chatId, 'Processing...', { replyToMessage: msg.message_id })

    const result = await TiktokDL(url)
    if (!result.result || !result.result.video || result.result.video.length === 0) {
      return bot.sendMessage(chatId, result.message || 'No video data available. Please check the TikTok URL.')
    }

    const video = pickVideo(result.result.video)
    if (!video?.url) {
      return bot.sendMessage(chatId, 'Invalid video data. Please try another TikTok URL.')
    }

    const namafile = result.result.id || 'unknown'
    const caption = result.result.description || ''
    const outputPath = path.resolve('download', `${namafile}.mp4`)

    if (!fs.existsSync(outputPath)) {
      await bot.sendMessage(chatId, 'Downloading video...')
      await downloadVideo(video.url, outputPath)
      console.log(`Download finished: ${outputPath}`)
    } else {
      console.log(`Using existing video: ${outputPath}`)
    }

    await bot.sendMessage(chatId, `Đang đăng lên Facebook bằng tài khoản: ${selectedAccount.accountName}`)
    console.log(`Starting Facebook upload for ${namafile} with account ${selectedAccount.accountName}`)
    activeVideoIds.add(namafile)
    let upload
    try {
      upload = await ReelsUpload(namafile, caption, {
        cookiePath: selectedAccount.cookiePath,
        accountName: selectedAccount.accountName
      })
    } finally {
      activeVideoIds.delete(namafile)
    }

    if (upload?.status === 'success') {
      updateUserStats(userId)
      return bot.sendMessage(chatId, upload.message || 'Video uploaded successfully.')
    }

    if (upload?.status === 'pending') {
      return bot.sendMessage(chatId, `Facebook publish not confirmed: ${upload.message}`)
    }

    return bot.sendMessage(chatId, `Upload failed: ${upload?.message || 'Unknown upload error'}`)
  } catch (error) {
    console.error('Error processing TikTok URL:', error)
    return bot.sendMessage(chatId, `An error occurred: ${error.message}`)
  }
}

bot.on(['/start', '/help'], (msg) => {
  if (rejectUnauthorized(msg)) return

  const helpMessage = `
TikTok Facebook Reuploader Bot

Cách dùng:
1. Gửi file cookie Facebook dạng JSON. Tên file sẽ là tên tài khoản.
2. Gửi link TikTok để đăng bằng tài khoản đang chọn.

Lệnh:
/accounts - Danh sách tài khoản
/use ten_tai_khoan - Chọn tài khoản
/remove ten_tai_khoan - Xóa tài khoản
/videos - Xem video đang lưu
/deletevideo id - Xóa một video
/deletevideo all - Xóa toàn bộ video
/stats - Thống kê hôm nay
/myid - Xem Telegram ID
/help - Xem hướng dẫn

Gioi han: khong gioi han so video moi ngay.
  `
  return bot.sendMessage(msg.chat.id, helpMessage)
})

bot.on('/stats', (msg) => {
  if (rejectUnauthorized(msg)) return

  const userId = msg.from.id
  const stats = userStats.get(userId)
  if (stats) {
    return bot.sendMessage(msg.chat.id, `Today (${stats.date}) you've processed ${stats.count} videos.`)
  }

  return bot.sendMessage(msg.chat.id, "You haven't processed any videos today.")
})

bot.on('/checkcookies', async (msg) => {
  if (rejectUnauthorized(msg)) return

  try {
    const selected = await getSelectedAccount(msg.from.id)
    if (!selected) {
      return bot.sendMessage(msg.chat.id, 'No Facebook account selected. Send a cookie JSON file first.')
    }

    const result = await inspectFacebookCookieFile(selected.cookiePath)
    const status = result.ok ? 'OK' : 'NOT OK'
    await bot.sendMessage(msg.chat.id, `Cookie file check for ${selected.accountName}: ${status}\n${result.message}`)

    if (!result.ok) return

    await bot.sendMessage(msg.chat.id, 'Running live Facebook login check...')
    const liveResult = await CheckFacebookCookie(selected.cookiePath)
    const liveStatus = liveResult.status === 'success' ? 'OK' : 'NOT OK'
    return bot.sendMessage(
      msg.chat.id,
      [
        `Live Facebook check for ${selected.accountName}: ${liveStatus}`,
        liveResult.message,
        liveResult.url ? `URL: ${liveResult.url}` : null,
        liveResult.title ? `Title: ${liveResult.title}` : null
      ].filter(Boolean).join('\n')
    )
  } catch (error) {
    return bot.sendMessage(msg.chat.id, `Could not check cookies: ${error.message}`)
  }
})

bot.on('/myid', (msg) => {
  return bot.sendMessage(msg.chat.id, `Telegram ID của bạn: ${msg.from.id}`)
})

bot.on('/accounts', async (msg) => {
  if (rejectUnauthorized(msg)) return

  try {
    const accounts = await listAccounts(msg.from.id)
    const selected = await getSelectedAccount(msg.from.id)
    if (accounts.length === 0) {
      return bot.sendMessage(msg.chat.id, 'Chưa có tài khoản. Hãy gửi file cookie Facebook dạng JSON.')
    }

    const lines = accounts.map((name) => `${selected?.accountName === name ? '✓' : '·'} ${name}`)
    return bot.sendMessage(msg.chat.id, `Tài khoản Facebook:\n${lines.join('\n')}`)
  } catch (error) {
    return bot.sendMessage(msg.chat.id, `Không thể đọc danh sách tài khoản: ${error.message}`)
  }
})

bot.on('/use', async (msg) => {
  if (rejectUnauthorized(msg)) return

  const accountName = sanitizeAccountName((msg.text || '').split(/\s+/).slice(1).join(' '))
  if (!(msg.text || '').trim().includes(' ')) {
    return bot.sendMessage(msg.chat.id, 'Cách dùng: /use ten_tai_khoan')
  }

  try {
    await selectAccount(msg.from.id, accountName)
    return bot.sendMessage(msg.chat.id, `Đã chọn tài khoản: ${accountName}`)
  } catch (error) {
    return bot.sendMessage(msg.chat.id, `Không tìm thấy tài khoản: ${accountName}`)
  }
})

bot.on('/remove', async (msg) => {
  if (rejectUnauthorized(msg)) return

  const hasName = (msg.text || '').trim().includes(' ')
  if (!hasName) {
    return bot.sendMessage(msg.chat.id, 'Cách dùng: /remove ten_tai_khoan')
  }

  const accountName = sanitizeAccountName((msg.text || '').split(/\s+/).slice(1).join(' '))
  try {
    const selected = await getSelectedAccount(msg.from.id)
    await fs.promises.unlink(getAccountPath(msg.from.id, accountName))
    if (selected?.accountName === accountName) {
      await fs.promises.unlink(getSelectionPath(msg.from.id)).catch(() => {})
    }
    return bot.sendMessage(msg.chat.id, `Đã xóa tài khoản: ${accountName}`)
  } catch (error) {
    return bot.sendMessage(msg.chat.id, `Không tìm thấy tài khoản: ${accountName}`)
  }
})

bot.on('/videos', async (msg) => {
  if (rejectUnauthorized(msg)) return

  try {
    const videos = await listStoredVideos()
    if (videos.length === 0) {
      return bot.sendMessage(msg.chat.id, 'Không có video nào đang lưu.')
    }

    const lines = videos.slice(0, 30).map((video) => {
      const sizeMb = (video.size / 1024 / 1024).toFixed(1)
      const status = activeVideoIds.has(video.id) ? ' (đang đăng)' : ''
      return `${video.id} - ${sizeMb} MB${status}`
    })
    const more = videos.length > 30 ? `\n...và ${videos.length - 30} video khác.` : ''
    return bot.sendMessage(msg.chat.id, `Video đang lưu (${videos.length}):\n${lines.join('\n')}${more}`)
  } catch (error) {
    return bot.sendMessage(msg.chat.id, `Không thể đọc danh sách video: ${error.message}`)
  }
})

bot.on(['/deletevideo', '/xoavideo'], async (msg) => {
  if (rejectUnauthorized(msg)) return

  const argument = (msg.text || '').trim().split(/\s+/).slice(1).join(' ')
  if (!argument) {
    return bot.sendMessage(msg.chat.id, 'Cách dùng: /deletevideo <id> hoặc /deletevideo all')
  }

  try {
    if (argument.toLowerCase() === 'all') {
      const videos = await listStoredVideos()
      const results = await Promise.all(videos.map((video) => deleteStoredVideo(video.id)))
      const deletedCount = results.filter((result) => result.deleted).length
      const activeCount = results.filter((result) => result.active).length
      const activeMessage = activeCount > 0 ? ` Bỏ qua ${activeCount} video đang đăng.` : ''
      return bot.sendMessage(msg.chat.id, `Đã xóa ${deletedCount} video.${activeMessage}`)
    }

    const videoId = path.basename(argument, path.extname(argument))
    const result = await deleteStoredVideo(videoId)
    if (result.active) {
      return bot.sendMessage(msg.chat.id, `Video ${videoId} đang được đăng nên chưa thể xóa.`)
    }
    if (!result.deleted) {
      return bot.sendMessage(msg.chat.id, `Không tìm thấy video: ${videoId}`)
    }
    return bot.sendMessage(msg.chat.id, `Đã xóa video: ${videoId}`)
  } catch (error) {
    return bot.sendMessage(msg.chat.id, `Không thể xóa video: ${error.message}`)
  }
})

bot.on('document', async (msg) => {
  if (rejectUnauthorized(msg)) return

  const document = msg.document
  const fileName = document?.file_name || ''
  if (path.extname(fileName).toLowerCase() !== '.json') {
    return bot.sendMessage(msg.chat.id, 'Bot chỉ nhận file cookie có đuôi .json.')
  }

  if ((document.file_size || 0) > MAX_COOKIE_FILE_SIZE) {
    return bot.sendMessage(msg.chat.id, 'File cookie quá lớn. Kích thước tối đa là 2 MB.')
  }

  try {
    await bot.sendMessage(msg.chat.id, 'Đang kiểm tra file cookie...')
    const telegramFile = await bot.getFile(document.file_id)
    const response = await axios.get(telegramFile.fileLink, {
      responseType: 'arraybuffer',
      maxContentLength: MAX_COOKIE_FILE_SIZE,
      maxBodyLength: MAX_COOKIE_FILE_SIZE
    })
    const rawJson = Buffer.from(response.data).toString('utf8').replace(/^\uFEFF/, '')
    const cookies = JSON.parse(rawJson)
    validateFacebookCookies(cookies)

    const accountName = sanitizeAccountName(fileName)
    const userDir = getUserAccountDir(msg.from.id)
    await fs.promises.mkdir(userDir, { recursive: true })
    await fs.promises.writeFile(
      getAccountPath(msg.from.id, accountName),
      JSON.stringify(cookies, null, 2),
      'utf8'
    )
    await selectAccount(msg.from.id, accountName)

    return bot.sendMessage(
      msg.chat.id,
      `Đã lưu và chọn tài khoản: ${accountName}\nBây giờ hãy gửi link TikTok để đăng video.`
    )
  } catch (error) {
    console.error('Error importing Facebook cookies:', error.message)
    return bot.sendMessage(msg.chat.id, `Không thể lưu tài khoản: ${error.message}`)
  }
})

bot.on('text', async (msg) => {
  if (rejectUnauthorized(msg)) return

  const body = msg.text || ''
  const tiktokRegex = /https?:\/\/(?:m|www|vm|vt)?\.?tiktok\.com\/\S+/
  const match = body.match(tiktokRegex)

  if (match) {
    await handleTikTokUrl(msg, match[0])
  }
})

bot.start()
if (ALLOWED_TELEGRAM_IDS.size === 0) {
  console.warn('WARNING: ALLOWED_TELEGRAM_IDS is empty. Anyone can use this bot.')
}
console.log('Telegram bot started. Send a Facebook cookie JSON file or TikTok URL to your bot.')
