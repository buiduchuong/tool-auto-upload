import axios from 'axios';
import fetch from 'node-fetch';
import asyncRetry from "async-retry";

const _tiktokapi = (Params) => `https://api22-normal-c-useast2a.tiktokv.com/aweme/v1/feed/?${Params}`

const fetchTikwmData = async (url) => {
  try {
    const { data } = await axios.post(
      "https://www.tikwm.com/api/",
      new URLSearchParams({ url }),
      {
        timeout: 15000,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        }
      }
    )

    if (data?.code !== 0 || !data?.data?.play) return null

    return {
      status: "success",
      result: {
        type: "video",
        id: data.data.id,
        createTime: data.data.create_time,
        description: data.data.title || "",
        hashtag: [],
        duration: toMinute(data.data.duration || 0),
        author: {
          uid: data.data.author?.id,
          username: data.data.author?.unique_id,
          nickname: data.data.author?.nickname,
          signature: "",
          region: data.data.region,
          avatarThumb: data.data.author?.avatar ? [data.data.author.avatar] : [],
          avatarMedium: data.data.author?.avatar ? [data.data.author.avatar] : [],
          url: data.data.author?.unique_id ? `https://tiktok.com/@${data.data.author.unique_id}` : ""
        },
        video: [data.data.play],
        cover: data.data.cover ? [data.data.cover] : [],
        dynamicCover: data.data.ai_dynamic_cover ? [data.data.ai_dynamic_cover] : [],
        originCover: data.data.origin_cover ? [data.data.origin_cover] : [],
        music: {
          id: data.data.music_info?.id,
          title: data.data.music_info?.title,
          author: data.data.music_info?.author,
          album: data.data.music_info?.album,
          playUrl: data.data.music ? [data.data.music] : [],
          coverLarge: data.data.music_info?.cover ? [data.data.music_info.cover] : [],
          coverMedium: data.data.music_info?.cover ? [data.data.music_info.cover] : [],
          coverThumb: data.data.music_info?.cover ? [data.data.music_info.cover] : [],
          duration: data.data.music_info?.duration
        }
      }
    }
  } catch (error) {
    return null
  }
}

const fetchTiktokData = async (ID) => {
  let data2
  try {
    await asyncRetry(
    async () => {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 10000)
      const res = await fetch(
        _tiktokapi(
          new URLSearchParams(
            withParams({
              aweme_id: ID
            })
          ).toString()
        ),
        {
          method: "GET",
          signal: controller.signal,
          headers: {
            "User-Agent": "com.ss.android.ugc.trill/494+Mozilla/5.0+(Linux;+Android+12;+2112123G+Build/SKQ1.211006.001;+wv)+AppleWebKit/537.36+(KHTML,+like+Gecko)+Version/4.0+Chrome/107.0.5304.105+Mobile+Safari/537.36"
          }
        }
      )
      clearTimeout(timeout)

      if (res.headers.get("content-length") !== "0") {
        const data = await res.json()
        if (data) {
          data2 = parseTiktokData(data)
          return
        }
      }

      throw new Error("Data is empty!")
    },
    { retries: 3, minTimeout: 1000, maxTimeout: 3000 }
    )
  } catch (error) {
    return null
  }

  return data2
}

export const TiktokDL = (url) => new Promise(async (resolve) => {
    url = url.replace("https://vm", "https://vt")
    axios
      .head(url, { timeout: 10000 })
      .then(async ({ request }) => {
        const { responseUrl } = request.res
        let ID = responseUrl.match(/\d{17,21}/g)
        if (ID === null)
          return resolve({
            status: "error",
            message: "Failed to fetch tiktok url. Make sure your tiktok url is correct!"
          })
        ID = ID[0]
        let data2 = await fetchTiktokData(ID)
        if (!data2) {
          const fallbackData = await fetchTikwmData(responseUrl)
          if (fallbackData) return resolve(fallbackData)

          return resolve({
            status: "error",
            message: "TikTok API did not return data. Try another public TikTok URL or try again later."
          })
        }
        if (!data2.content) {
          return resolve({
            status: "error",
            message: "Failed to fetch tiktok data. Make sure your tiktok url is correct!"
          })
        }

        const { content, author, music } = data2

        // Download Result
        if (content.image_post_info) {
          // Images or Slide Result
          resolve({
            status: "success",
            result: {
              type: "image",
              id: content.aweme_id,
              createTime: content.create_time,
              description: content.desc,
              hashtag: content.text_extra.filter((x) => x.hashtag_name !== undefined).map((v) => v.hashtag_name),
              author,
              images: content.image_post_info.images.map((v) => v.display_image.url_list[0]),
              music
            }
          })
        } else {
          // Video Result
          resolve({
            status: "success",
            result: {
              type: "video",
              id: content.aweme_id,
              createTime: content.create_time,
              description: content.desc,
              hashtag: content.text_extra.filter((x) => x.hashtag_name !== undefined).map((v) => v.hashtag_name),
              duration: toMinute(content.duration),
              author,
              video: content.video.play_addr.url_list,
              cover: content.video.cover.url_list,
              dynamicCover: content.video.dynamic_cover.url_list,
              originCover: content.video.origin_cover.url_list,
              music
            }
          })
        }
        })
      .catch((e) => resolve({ status: "error", message: e.message }))
  })

  const parseTiktokData = (data) => {
    let content = data?.aweme_list
    if (!content) return { content: null }
  
    content = content[0]
  
    // Author Result
    const author = {
      uid: content.author.uid,
      username: content.author.unique_id,
      nickname: content.author.nickname,
      signature: content.author.signature,
      region: content.author.region,
      avatarThumb: content.author.avatar_thumb.url_list,
      avatarMedium: content.author.avatar_medium.url_list,
      url: `https://tiktok.com/@${content.author.unique_id}`
    }
  
    // Music Result
    const music = {
      id: content.music.id,
      title: content.music.title,
      author: content.music.author,
      album: content.music.album,
      playUrl: content.music.play_url.url_list,
      coverLarge: content.music.cover_large.url_list,
      coverMedium: content.music.cover_medium.url_list,
      coverThumb: content.music.cover_thumb.url_list,
      duration: content.music.duration
    }
  
    return { content, author, music }
  }

  const withParams = (args) => {
    return {
      ...args,
      version_name: "1.1.9",
      version_code: "2018111632",
      build_number: "1.1.9",
      manifest_version_code: "2018111632",
      update_version_code: "2018111632",
      openudid: randomChar("0123456789abcdef", 16),
      uuid: randomChar("1234567890", 16),
      _rticket: Date.now() * 1000,
      ts: Date.now(),
      device_brand: "Google",
      device_type: "Pixel 4",
      device_platform: "android",
      resolution: "1080*1920",
      dpi: 420,
      os_version: "10",
      os_api: "29",
      carrier_region: "US",
      sys_region: "US",
      region: "US",
      app_name: "trill",
      app_language: "en",
      language: "en",
      timezone_name: "America/New_York",
      timezone_offset: "-14400",
      channel: "googleplay",
      ac: "wifi",
      mcc_mnc: "310260",
      is_my_cn: 0,
      aid: 1180,
      ssmix: "a",
      as: "a1qwert123",
      cp: "cbfhckdckkde1"
    }
  }
  
  const randomChar = (char, range) => {
    let chars = ""
  
    for (let i = 0; i < range; i++) {
      chars += char[Math.floor(Math.random() * char.length)]
    }
  
    return chars
  }

  const toMinute = (duration) => {
    const mins = ~~((duration % 3600) / 60)
    const secs = ~~duration % 60
  
    let ret = ""
  
    ret += "" + mins + ":" + (secs < 10 ? "0" : "")
    ret += "" + secs
  
    return ret
  }
