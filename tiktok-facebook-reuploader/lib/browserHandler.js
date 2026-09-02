import puppeteer from 'puppeteer'
import { executablePath } from 'puppeteer'
import moment from 'moment'
import delay from 'delay'
import fs from 'fs-extra'
import path from 'path'

const browserPageOpt = { waitUntil: 'domcontentloaded', timeout: 90000 }

function getBrowserOptions() {
  return {
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || executablePath(),
    headless: process.env.PUPPETEER_HEADLESS === 'true',
    timeout: 60000,
    dumpio: process.env.PUPPETEER_DEBUG === 'true',
    args: [
      '--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"',
      '--no-sandbox',
      '--mute-audio',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--disable-extensions'
    ]
  }
}

const oldTextAreaSelector = '//*[starts-with(@id, "mount")]/div/div[1]/div/div[3]/div/div/div[1]/form/div/div/div[1]/div/div[2]/div[1]/div[2]/div/div/div/div/div[1]/div[1]/div[1]'

function printLog(str) {
  const date = moment().format('HH:mm:ss')
  console.log(`[${date}] ${str}`)
}

async function withTimeout(promise, timeout, message) {
  let timer
  try {
    return await Promise.race([
      promise,
      new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error(message)), timeout)
      })
    ])
  } finally {
    clearTimeout(timer)
  }
}

async function checkSession(cookieFilePath) {
  try {
    const fullPath = path.resolve(cookieFilePath)
    const cookies = JSON.parse(await fs.readFile(fullPath))
    return Array.isArray(cookies) && cookies.length > 0
  } catch (err) {
    return false
  }
}

function getCookieKey(cookie) {
  return `${cookie.name}|${cookie.domain || ''}|${cookie.path || '/'}`
}

async function refreshCookieFile(page, cookieFilePath) {
  try {
    const fullPath = path.resolve(cookieFilePath)
    const storedCookies = JSON.parse(await fs.readFile(fullPath))
    const browserCookies = await page.cookies('https://www.facebook.com', 'https://facebook.com')

    if (!browserCookies.some((cookie) => cookie.name === 'c_user') || !browserCookies.some((cookie) => cookie.name === 'xs')) {
      printLog('WARN: Browser did not return a complete logged-in Facebook cookie set. Cookie file was not updated.')
      return false
    }

    const merged = new Map()
    for (const cookie of Array.isArray(storedCookies) ? storedCookies : []) {
      merged.set(getCookieKey(cookie), cookie)
    }
    for (const cookie of browserCookies) {
      merged.set(getCookieKey(cookie), cookie)
    }

    await fs.ensureDir(path.dirname(fullPath))
    await fs.writeFile(fullPath, JSON.stringify([...merged.values()], null, 2), 'utf8')
    printLog(`Facebook cookies refreshed: ${fullPath}`)
    return true
  } catch (error) {
    printLog(`WARN: Could not refresh Facebook cookies: ${error.message}`)
    return false
  }
}

function getFacebookAccessIssue(url) {
  const normalizedUrl = String(url || '').toLowerCase()
  if (normalizedUrl.includes('/login')) {
    return 'Facebook redirected to login. The cookie file is structurally OK, but the session is not accepted by Facebook.'
  }
  if (normalizedUrl.includes('/checkpoint')) {
    return 'Facebook redirected to checkpoint. Open Facebook manually and finish the verification, then export cookies again.'
  }
  if (normalizedUrl.includes('/recover') || normalizedUrl.includes('/confirmemail') || normalizedUrl.includes('/two_factor')) {
    return `Facebook redirected to an account verification page: ${url}`
  }
  return null
}

export const CheckFacebookCookie = (cookieFilePath, options = {}) => new Promise(async (resolve) => {
  let browser
  let page
  const cookiePath = path.resolve(cookieFilePath)

  try {
    const resCheckSession = await checkSession(cookiePath)
    if (!resCheckSession) {
      return resolve({
        status: 'error',
        message: `Facebook session not found in ${cookiePath}.`
      })
    }

    const launchOptions = getBrowserOptions()
    printLog(`Checking Facebook cookie (${launchOptions.headless ? 'headless' : 'visible'})...`)
    browser = await withTimeout(
      puppeteer.launch(launchOptions),
      70000,
      'Chrome did not start within 70 seconds.'
    )
    page = await browser.newPage()
    await page.setCookie(...JSON.parse(await fs.readFile(cookiePath)))
    await page.goto(options.url || 'https://www.facebook.com/reels/create', browserPageOpt)
    await delay(3000)

    const currentUrl = page.url()
    const issue = getFacebookAccessIssue(currentUrl)
    const title = await page.title().catch(() => '')

    if (issue) {
      await saveDebugScreenshot(page, 'facebook-cookie-live-check-failed.png')
      await browser.close()
      return resolve({
        status: 'error',
        url: currentUrl,
        title,
        message: issue
      })
    }

    await refreshCookieFile(page, cookiePath)
    await browser.close()
    return resolve({
      status: 'success',
      url: currentUrl,
      title,
      message: 'Facebook accepted this cookie in a live browser check.'
    })
  } catch (error) {
    if (page) await saveDebugScreenshot(page, 'facebook-cookie-live-check-error.png')
    if (browser) await browser.close().catch(() => {})
    return resolve({
      status: 'error',
      message: error.message || 'Could not check Facebook cookie in browser.'
    })
  }
})

function normalizeText(value) {
  return (value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function isTransientPageError(error) {
  const message = String(error?.message || error)
  return (
    message.includes('Execution context was destroyed') ||
    message.includes('Cannot find context with specified id') ||
    message.includes('Node is detached from document') ||
    message.includes('Execution context is not available in detached frame')
  )
}

function isDetachedNodeError(error) {
  return String(error?.message || error).includes('Node is detached from document')
}

async function clickButtonByText(page, labels, timeout = 30000) {
  const normalizedLabels = labels.map(normalizeText)
  const deadline = Date.now() + timeout

  while (Date.now() < deadline) {
    let candidates
    try {
      candidates = await page.$$('[role="button"], button, div[aria-label]')
    } catch (error) {
      if (!isTransientPageError(error)) throw error
      printLog('Facebook navigated while finding a button. Retrying...')
      await delay(1000)
      continue
    }
    const matches = []

    for (const candidate of candidates) {
      let info
      try {
        info = await candidate.evaluate((el) => ({
          text: el.innerText || el.textContent || '',
          ariaLabel: el.getAttribute('aria-label') || '',
          disabled: el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled'),
          visible: (() => {
            const rect = el.getBoundingClientRect()
            const style = window.getComputedStyle(el)
            return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
          })()
        }))
      } catch (error) {
        if (isTransientPageError(error)) continue
        throw error
      }
      const text = normalizeText(info.text)
      const ariaLabel = normalizeText(info.ariaLabel)
      const combinedText = normalizeText(`${info.text} ${info.ariaLabel}`)
      const exactMatch = normalizedLabels.some((label) => text === label || ariaLabel === label)
      const looseMatch = normalizedLabels.some((label) => combinedText === label)

      if ((exactMatch || looseMatch) && !info.disabled && info.visible) {
        matches.push(candidate)
      }
    }

    const button = matches[matches.length - 1]
    if (button) {
      let clickedInfo
      try {
        clickedInfo = await button.evaluate((el) => ({
          text: el.innerText || el.textContent || '',
          ariaLabel: el.getAttribute('aria-label') || ''
        }))
      } catch (error) {
        if (!isTransientPageError(error)) throw error
        await delay(1000)
        continue
      }
      printLog(`Clicked button: ${clickedInfo.text || clickedInfo.ariaLabel}`)
      try {
        await button.click()
      } catch (error) {
        if (!isTransientPageError(error)) throw error
        if (isDetachedNodeError(error)) {
          printLog('Facebook replaced the button before it was clicked. Finding the new button...')
          await delay(1000)
          continue
        }
        printLog('Facebook navigated immediately after the click. Continuing...')
      }
      return true
    }

    await delay(500)
  }

  return false
}

async function uploadVideoFile(page, filePath) {
  let fileInput = await page.$('input[type="file"]')

  if (!fileInput) {
    await clickButtonByText(page, [
      'Add video',
      'Upload video',
      'Select video',
      'Choose file',
      'Them video',
      'Tai video',
      'Chon tep',
      'Chon video',
      'Thêm video',
      'Tải video',
      'Chọn tệp',
      'Chọn video'
    ], 10000)
    fileInput = await page.waitForSelector('input[type="file"]', { timeout: 30000 })
  }

  await fileInput.uploadFile(filePath)
}

async function typeCaption(page, caption) {
  if (!caption) return

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const oldTextArea = await page.$x(oldTextAreaSelector)
      if (oldTextArea[0]) {
        await oldTextArea[0].click()
        await oldTextArea[0].type(caption)
        return
      }

      const editors = await page.$$('[contenteditable="true"], textarea')
      if (editors.length === 0) {
        printLog('WARN: Caption field not found, skipping caption.')
        return
      }

      const editor = editors[editors.length - 1]
      await editor.click()
      await page.keyboard.type(caption)
      return
    } catch (error) {
      if (!isTransientPageError(error) || attempt === 3) throw error
      printLog('Facebook navigated during the caption step. Retrying...')
      await delay(1500)
    }
  }
}

async function saveDebugScreenshot(page, name) {
  const filePath = path.resolve(name)
  try {
    await page.screenshot({ path: filePath, fullPage: true })
    printLog(`Debug screenshot saved: ${filePath}`)
  } catch (err) {
    printLog(`WARN: Could not save debug screenshot: ${err.message}`)
  }
}

async function waitForPublishResult(page, timeout = 180000) {
  const successLabels = [
    'your reel has been shared',
    'your post has been shared',
    'your reel is now published',
    'your reel is ready to view',
    'reel cua ban da duoc chia se',
    'bai viet cua ban da duoc chia se',
    'ban co the xem thuoc phim roi',
    'hay chia se voi ban be nhe',
    'da chia se reel',
    'da dang reel',
    'da dang bai viet'
  ].map(normalizeText)

  const processingLabels = [
    'your reel is being processed',
    'we will let you know when your reel is ready to view',
    'we\'ll let you know when your reel is ready to view',
    'your video is processing',
    'thuoc phim cua ban dang duoc xu ly',
    'chung toi se cho ban biet khi co the xem thuoc phim nay'
  ].map(normalizeText)

  const errorLabels = [
    'could not upload',
    'couldn\'t upload',
    'upload failed',
    'something went wrong',
    'try again',
    'khong the tai',
    'tai len khong thanh cong',
    'da xay ra loi',
    'thu lai'
  ].map(normalizeText)

  const deadline = Date.now() + timeout

  while (Date.now() < deadline) {
    let pageText
    try {
      pageText = await page.evaluate(() => {
        const bodyText = document.body?.innerText || ''
        const ariaText = Array.from(document.querySelectorAll('[aria-label]'))
          .map((el) => el.getAttribute('aria-label') || '')
          .join(' ')
        return `${bodyText} ${ariaText}`
      })
    } catch (error) {
      if (!isTransientPageError(error)) throw error
      printLog('Facebook navigated while checking publish status. Retrying...')
      await delay(1500)
      continue
    }
    const text = normalizeText(pageText)

    const matchedError = errorLabels.find((label) => text.includes(label))
    if (matchedError) return { status: 'error', message: `Facebook showed an upload error: ${matchedError}` }

    const matchedProcessing = processingLabels.find((label) => text.includes(label))
    if (matchedProcessing) {
      return {
        status: 'success',
        facebookStatus: 'processing',
        message: 'Facebook báo: Thước phim của bạn đang được xử lý. Facebook sẽ thông báo khi có thể xem thước phim này.'
      }
    }

    const matchedSuccess = successLabels.find((label) => text.includes(label))
    if (matchedSuccess) {
      return {
        status: 'success',
        facebookStatus: 'published',
        message: 'Facebook xác nhận thước phim đã được đăng.'
      }
    }

    await delay(1000)
  }

  return {
    status: 'pending',
    message: 'Post button was clicked, but Facebook did not show a publish confirmation before timeout.'
  }
}

export const ReelsUpload = (namafile, caption, options = {}) => new Promise(async (resolve) => {
  let browser
  let page
  const cookiePath = path.resolve(options.cookiePath || './cookies.json')

  try {
    const launchOptions = getBrowserOptions()
    printLog(`Starting Chrome (${launchOptions.headless ? 'headless' : 'visible'})...`)
    browser = await withTimeout(
      puppeteer.launch(launchOptions),
      70000,
      'Chrome did not start within 70 seconds.'
    )
    printLog('Chrome started, creating a page...')
    page = await withTimeout(
      browser.newPage(),
      30000,
      'Chrome started but could not create a page within 30 seconds.'
    )
    printLog('Browser page created.')

    const resCheckSession = await checkSession(cookiePath)
    if (!resCheckSession) {
      const err = `INFO: Facebook session not found in ${cookiePath}.`
      printLog(err)
      await browser.close()
      return resolve({ status: 'error', message: err })
    }

    const accountLabel = options.accountName ? ` for account "${options.accountName}"` : ''
    printLog(`INFO: Session found${accountLabel}, opening Facebook...`)
    await page.setCookie(...JSON.parse(await fs.readFile(cookiePath)))
    await page.goto('https://www.facebook.com/reels/create', browserPageOpt)

    if (page.url().includes('/login')) {
      await saveDebugScreenshot(page, 'facebook-login-required.png')
      await browser.close()
      return resolve({ status: 'error', message: 'Facebook cookie expired or invalid. Please export cookies again.' })
    }

    printLog('Facebook opened.')
    await refreshCookieFile(page, cookiePath)
    const videoPath = path.resolve(`./download/${namafile}.mp4`)
    await uploadVideoFile(page, videoPath)
    printLog(`Uploaded file to Facebook form: ${namafile}.mp4`)

    await delay(30000)

    const firstNextClicked = await clickButtonByText(page, ['Next', 'Tiep', 'Tiếp'], 120000)
    if (!firstNextClicked) {
      await saveDebugScreenshot(page, 'facebook-next-step-1-error.png')
      await refreshCookieFile(page, cookiePath)
      await browser.close()
      return resolve({ status: 'error', message: 'Could not find the first Next button on Facebook.' })
    }

    await delay(3000)

    const secondNextClicked = await clickButtonByText(page, ['Next', 'Tiep', 'Tiếp'], 60000)
    if (!secondNextClicked) {
      printLog('WARN: Second Next button not found, trying to continue.')
    } else {
      await delay(3000)
    }

    await typeCaption(page, caption)
    printLog('Caption step finished.')

    await delay(2000)

    const publishClicked = await clickButtonByText(page, [
      'Publish',
      'Post',
      'Share',
      'Dang',
      'Đăng',
      'Chia se',
      'Chia sẻ'
    ], 45000)

    if (!publishClicked) {
      await saveDebugScreenshot(page, 'facebook-publish-error.png')
      await refreshCookieFile(page, cookiePath)
      await browser.close()
      return resolve({ status: 'error', message: 'Could not find the Publish/Post button on Facebook.' })
    }

    printLog('Post clicked, waiting for Facebook to finish...')
    const publishResult = await waitForPublishResult(page)
    await refreshCookieFile(page, cookiePath)

    if (publishResult.status !== 'success') {
      printLog(`WARN: ${publishResult.message}`)
      await saveDebugScreenshot(page, 'facebook-publish-timeout.png')
      await browser.close()
      return resolve(publishResult)
    }

    await browser.close()
    printLog('Upload flow finished.')
    return resolve(publishResult)
  } catch (err) {
    printLog(err.stack || err.message || err)
    if (page) await saveDebugScreenshot(page, 'facebook-upload-error.png')
    if (page) await refreshCookieFile(page, cookiePath)
    if (browser) await browser.close().catch(() => {})
    return resolve({ status: 'error', message: err.message || 'Video upload failed.' })
  }
})
