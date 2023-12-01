import itertools
import re
from urllib.parse import urlparse, parse_qs

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    dict_get,
    int_or_none,
    join_nonempty,
    merge_dicts,
    parse_duration,
    traverse_obj,
    try_get,
    unified_timestamp,
    update_url_query,
    unified_strdate,
)


class NaverBaseIE(InfoExtractor):
    _CAPTION_EXT_RE = r'\.(?:ttml|vtt)'

    @staticmethod  # NB: Used in WeverseIE
    def process_subtitles(vod_data, process_url):
        ret = {'subtitles': {}, 'automatic_captions': {}}
        for caption in traverse_obj(vod_data, ('captions', 'list', ...)):
            caption_url = caption.get('source')
            if not caption_url:
                continue
            type_ = 'automatic_captions' if caption.get('type') == 'auto' else 'subtitles'
            lang = caption.get('locale') or join_nonempty('language', 'country', from_dict=caption) or 'und'
            if caption.get('type') == 'fan':
                lang += '_fan%d' % next(i for i in itertools.count(1) if f'{lang}_fan{i}' not in ret[type_])
            ret[type_].setdefault(lang, []).extend({
                'url': sub_url,
                'name': join_nonempty('label', 'fanName', from_dict=caption, delim=' - '),
            } for sub_url in process_url(caption_url))
        return ret

    def _extract_video_info(self, video_id, vid, key):
        video_data = self._download_json(
            'http://play.rmcnmv.naver.com/vod/play/v2.0/' + vid,
            video_id, query={
                'key': key,
            })
        meta = video_data['meta']
        title = meta['subject']
        formats = []
        get_list = lambda x: try_get(video_data, lambda y: y[x + 's']['list'], list) or []

        def extract_formats(streams, stream_type, query={}):
            for stream in streams:
                stream_url = stream.get('source')
                if not stream_url:
                    continue
                stream_url = update_url_query(stream_url, query)
                encoding_option = stream.get('encodingOption', {})
                bitrate = stream.get('bitrate', {})
                formats.append({
                    'format_id': '%s_%s' % (stream.get('type') or stream_type, dict_get(encoding_option, ('name', 'id'))),
                    'url': stream_url,
                    'ext': 'mp4',
                    'width': int_or_none(encoding_option.get('width')),
                    'height': int_or_none(encoding_option.get('height')),
                    'vbr': int_or_none(bitrate.get('video')),
                    'abr': int_or_none(bitrate.get('audio')),
                    'filesize': int_or_none(stream.get('size')),
                    'protocol': 'm3u8_native' if stream_type == 'HLS' else None,
                })

        extract_formats(get_list('video'), 'H264')
        for stream_set in video_data.get('streams', []):
            query = {}
            for param in stream_set.get('keys', []):
                query[param['name']] = param['value']
            stream_type = stream_set.get('type')
            videos = stream_set.get('videos')
            if videos:
                extract_formats(videos, stream_type, query)
            elif stream_type == 'HLS':
                stream_url = stream_set.get('source')
                if not stream_url:
                    continue
                formats.extend(self._extract_m3u8_formats(
                    update_url_query(stream_url, query), video_id,
                    'mp4', 'm3u8_native', m3u8_id=stream_type, fatal=False))

        replace_ext = lambda x, y: re.sub(self._CAPTION_EXT_RE, '.' + y, x)

        def get_subs(caption_url):
            if re.search(self._CAPTION_EXT_RE, caption_url):
                return [
                    replace_ext(caption_url, 'ttml'),
                    replace_ext(caption_url, 'vtt'),
                ]
            return [caption_url]

        user = meta.get('user', {})

        return {
            'id': video_id,
            'title': title,
            'formats': formats,
            'thumbnail': try_get(meta, lambda x: x['cover']['source']),
            'view_count': int_or_none(meta.get('count')),
            'uploader_id': user.get('id'),
            'uploader': user.get('name'),
            'uploader_url': user.get('url'),
            **self.process_subtitles(video_data, get_subs),
        }


class NaverIE(NaverBaseIE):
    _VALID_URL = r'https?://(?:m\.)?tv(?:cast)?\.naver\.com/(?:v|embed)/(?P<id>\d+)'
    _GEO_BYPASS = False
    _TESTS = [{
        'url': 'http://tv.naver.com/v/81652',
        'info_dict': {
            'id': '81652',
            'ext': 'mp4',
            'title': '[9월 모의고사 해설강의][수학_김상희] 수학 A형 16~20번',
            'description': '메가스터디 수학 김상희 선생님이 9월 모의고사 수학A형 16번에서 20번까지 해설강의를 공개합니다.',
            'timestamp': 1378200754,
            'upload_date': '20130903',
            'uploader': '메가스터디, 합격불변의 법칙',
            'uploader_id': 'megastudy',
        },
    }, {
        'url': 'http://tv.naver.com/v/395837',
        'md5': '8a38e35354d26a17f73f4e90094febd3',
        'info_dict': {
            'id': '395837',
            'ext': 'mp4',
            'title': '9년이 지나도 아픈 기억, 전효성의 아버지',
            'description': 'md5:eb6aca9d457b922e43860a2a2b1984d3',
            'timestamp': 1432030253,
            'upload_date': '20150519',
            'uploader': '4가지쇼 시즌2',
            'uploader_id': 'wrappinguser29',
        },
        'skip': 'Georestricted',
    }, {
        'url': 'http://tvcast.naver.com/v/81652',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        content = self._download_json(
            'https://tv.naver.com/api/json/v/' + video_id,
            video_id, headers=self.geo_verification_headers())
        player_info_json = content.get('playerInfoJson') or {}
        current_clip = player_info_json.get('currentClip') or {}

        vid = current_clip.get('videoId')
        in_key = current_clip.get('inKey')

        if not vid or not in_key:
            player_auth = try_get(player_info_json, lambda x: x['playerOption']['auth'])
            if player_auth == 'notCountry':
                self.raise_geo_restricted(countries=['KR'])
            elif player_auth == 'notLogin':
                self.raise_login_required()
            raise ExtractorError('couldn\'t extract vid and key')
        info = self._extract_video_info(video_id, vid, in_key)
        info.update({
            'description': clean_html(current_clip.get('description')),
            'timestamp': int_or_none(current_clip.get('firstExposureTime'), 1000),
            'duration': parse_duration(current_clip.get('displayPlayTime')),
            'like_count': int_or_none(current_clip.get('recommendPoint')),
            'age_limit': 19 if current_clip.get('adult') else None,
        })
        return info


class NaverLiveIE(InfoExtractor):
    IE_NAME = 'Naver:live'
    _VALID_URL = r'https?://(?:m\.)?tv(?:cast)?\.naver\.com/l/(?P<id>\d+)'
    _GEO_BYPASS = False
    _TESTS = [{
        'url': 'https://tv.naver.com/l/52010',
        'info_dict': {
            'id': '52010',
            'ext': 'mp4',
            'title': '[LIVE] 뉴스특보 : "수도권 거리두기, 2주간 2단계로 조정"',
            'description': 'md5:df7f0c237a5ed5e786ce5c91efbeaab3',
            'channel_id': 'NTV-ytnnews24-0',
            'start_time': 1597026780000,
        },
    }, {
        'url': 'https://tv.naver.com/l/51549',
        'info_dict': {
            'id': '51549',
            'ext': 'mp4',
            'title': '연합뉴스TV - 코로나19 뉴스특보',
            'description': 'md5:c655e82091bc21e413f549c0eaccc481',
            'channel_id': 'NTV-yonhapnewstv-0',
            'start_time': 1596406380000,
        },
    }, {
        'url': 'https://tv.naver.com/l/54887',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        page = self._download_webpage(url, video_id, 'Downloading Page', 'Unable to download Page')
        secure_url = self._search_regex(r'sApiF:\s+(?:"|\')([^"\']+)', page, 'secureurl')

        info = self._extract_video_info(video_id, secure_url)
        info.update({
            'description': self._og_search_description(page)
        })

        return info

    def _extract_video_info(self, video_id, url):
        video_data = self._download_json(url, video_id, headers=self.geo_verification_headers())
        meta = video_data.get('meta')
        status = meta.get('status')

        if status == 'CLOSED':
            raise ExtractorError('Stream is offline.', expected=True)
        elif status != 'OPENED':
            raise ExtractorError('Unknown status %s' % status)

        title = meta.get('title')
        stream_list = video_data.get('streams')

        if stream_list is None:
            raise ExtractorError('Could not get stream data.', expected=True)

        formats = []
        for quality in stream_list:
            if not quality.get('url'):
                continue

            prop = quality.get('property')
            if prop.get('abr'):  # This abr doesn't mean Average audio bitrate.
                continue

            formats.extend(self._extract_m3u8_formats(
                quality.get('url'), video_id, 'mp4',
                m3u8_id=quality.get('qualityId'), live=True
            ))

        return {
            'id': video_id,
            'title': title,
            'formats': formats,
            'channel_id': meta.get('channelId'),
            'channel_url': meta.get('channelUrl'),
            'thumbnail': meta.get('imgUrl'),
            'start_time': meta.get('startTime'),
            'categories': [meta.get('categoryId')],
            'is_live': True
        }


class NaverNowIE(NaverBaseIE):
    IE_NAME = 'navernow'
    _VALID_URL = r'https?://now\.naver\.com/s/now\.(?P<id>\w+)'
    _API_URL = 'https://apis.naver.com/now_web/oldnow_web/v4'
    _TESTS = [{
        'url': 'https://now.naver.com/s/now.4759?shareReplayId=26331132#replay=',
        'md5': 'e05854162c21c221481de16b2944a0bc',
        'info_dict': {
            'id': '4759-26331132',
            'title': '아이키X노제\r\n💖꽁냥꽁냥💖(1)',
            'ext': 'mp4',
            'thumbnail': r're:^https?://.*\.jpg',
            'timestamp': 1650369600,
            'upload_date': '20220419',
            'uploader_id': 'now',
            'view_count': int,
            'uploader_url': 'https://now.naver.com/show/4759',
            'uploader': '아이키의 떰즈업',
        },
        'params': {
            'noplaylist': True,
        }
    }, {
        'url': 'https://now.naver.com/s/now.4759?shareHightlight=26601461#highlight=',
        'md5': '9f6118e398aa0f22b2152f554ea7851b',
        'info_dict': {
            'id': '4759-26601461',
            'title': '아이키: 나 리정한테 흔들렸어,,, 질투 폭발하는 노제 여보😾 [아이키의 떰즈업]ㅣ네이버 NOW.',
            'ext': 'mp4',
            'thumbnail': r're:^https?://.*\.jpg',
            'upload_date': '20220504',
            'timestamp': 1651648311,
            'uploader_id': 'now',
            'view_count': int,
            'uploader_url': 'https://now.naver.com/show/4759',
            'uploader': '아이키의 떰즈업',
        },
        'params': {
            'noplaylist': True,
        },
    }, {
        'url': 'https://now.naver.com/s/now.4759',
        'info_dict': {
            'id': '4759',
            'title': '아이키의 떰즈업',
        },
        'playlist_mincount': 101
    }, {
        'url': 'https://now.naver.com/s/now.4759?shareReplayId=26331132#replay',
        'info_dict': {
            'id': '4759',
            'title': '아이키의 떰즈업',
        },
        'playlist_mincount': 101,
    }, {
        'url': 'https://now.naver.com/s/now.4759?shareHightlight=26601461#highlight=',
        'info_dict': {
            'id': '4759',
            'title': '아이키의 떰즈업',
        },
        'playlist_mincount': 101,
    }, {
        'url': 'https://now.naver.com/s/now.kihyunplay?shareReplayId=30573291#replay',
        'only_matching': True,
    }]

    def _extract_replay(self, show_id, replay_id):
        vod_info = self._download_json(f'{self._API_URL}/shows/now.{show_id}/vod/{replay_id}', replay_id)
        in_key = self._download_json(f'{self._API_URL}/shows/now.{show_id}/vod/{replay_id}/inkey', replay_id)['inKey']
        return merge_dicts({
            'id': f'{show_id}-{replay_id}',
            'title': traverse_obj(vod_info, ('episode', 'title')),
            'timestamp': unified_timestamp(traverse_obj(vod_info, ('episode', 'start_time'))),
            'thumbnail': vod_info.get('thumbnail_image_url'),
        }, self._extract_video_info(replay_id, vod_info['video_id'], in_key))

    def _extract_show_replays(self, show_id):
        page_size = 15
        page = 1
        while True:
            show_vod_info = self._download_json(
                f'{self._API_URL}/vod-shows/now.{show_id}', show_id,
                query={'page': page, 'page_size': page_size},
                note=f'Downloading JSON vod list for show {show_id} - page {page}'
            )['response']['result']
            for v in show_vod_info.get('vod_list') or []:
                yield self._extract_replay(show_id, v['id'])

            if len(show_vod_info.get('vod_list') or []) < page_size:
                break
            page += 1

    def _extract_show_highlights(self, show_id, highlight_id=None):
        page_size = 10
        page = 1
        while True:
            highlights_videos = self._download_json(
                f'{self._API_URL}/shows/now.{show_id}/highlights/videos/', show_id,
                query={'page': page, 'page_size': page_size},
                note=f'Downloading JSON highlights for show {show_id} - page {page}')

            for highlight in highlights_videos.get('results') or []:
                if highlight_id and highlight.get('clip_no') != int(highlight_id):
                    continue
                yield merge_dicts({
                    'id': f'{show_id}-{highlight["clip_no"]}',
                    'title': highlight.get('title'),
                    'timestamp': unified_timestamp(highlight.get('regdate')),
                    'thumbnail': highlight.get('thumbnail_url'),
                }, self._extract_video_info(highlight['clip_no'], highlight['video_id'], highlight['video_inkey']))

            if len(highlights_videos.get('results') or []) < page_size:
                break
            page += 1

    def _extract_highlight(self, show_id, highlight_id):
        try:
            return next(self._extract_show_highlights(show_id, highlight_id))
        except StopIteration:
            raise ExtractorError(f'Unable to find highlight {highlight_id} for show {show_id}')

    def _real_extract(self, url):
        show_id = self._match_id(url)
        qs = parse_qs(urlparse(url).query)

        if not self._yes_playlist(show_id, qs.get('shareHightlight')):
            return self._extract_highlight(show_id, qs['shareHightlight'][0])
        elif not self._yes_playlist(show_id, qs.get('shareReplayId')):
            return self._extract_replay(show_id, qs['shareReplayId'][0])

        show_info = self._download_json(
            f'{self._API_URL}/shows/now.{show_id}/', show_id,
            note=f'Downloading JSON vod list for show {show_id}')

        return self.playlist_result(
            itertools.chain(self._extract_show_replays(show_id), self._extract_show_highlights(show_id)),
            show_id, show_info.get('title'))


class NaverNowWatchIE(NaverBaseIE):
    IE_NAME = 'navernowwatch'
    # Video ids seem to be exactly 12 characters for now but this hasn't been thoroughly tested
    # so a wider id length is allowed here
    _VALID_URL = r'https?://now\.naver\.com/watch/(?P<id>[0-9A-Za-z_-]{10,14})'
    _API_URL = 'https://apis.naver.com/now_web2/now_web_api/v1/content'
    _TESTS = [{
        'url': 'https://now.naver.com/watch/ELt-oy2EfLHs',
        'md5': 'f6dc239cc08d7ac0d4a3da0794442559',
        'info_dict': {
            'id': 'ELt-oy2EfLHs',
            'title': '[NPOP EP.14] VIXX 외의 다른 건 Forget🌟 l 2023.11.29',
            'ext': 'mp4',
            'thumbnail': r're:^https?://.*\.jpg',
            'timestamp': 1701159669,
            'upload_date': '20231128',
            'uploader_id': 'npop',
            'view_count': int,
            # The channelUrl from the API is https://m.tv.naver.com/npop but this redirects to https://now.naver.com/s/npop
            'uploader_url': 'https://m.tv.naver.com/npop',
            'uploader': 'NPOP (엔팝)',
            'duration': 1268,
            'like_count': 186,
            'description': '[NPOP EP.14] VIXX 외의 다른 건 Forget🌟 l 2023.11.29\r\n\r\nEP.14의 주인공 VIXX(빅스)!💙\r\n컴백한 VIXX의 우당탕탕 STAY N부터 무대장인 STAGE N까지!\r\n내 아티스트의 다양한 모습을 NPOP에서 함께하세요!\r\n\r\n_\r\n💿\"두 개의 공간, 하나로 연결된 우리\"\r\n아티스트와 팬이 함께 만들어가는 월간 K-POP 차트쇼✨\r\n\r\n온라인 팬들과 소통하며 진행되는 관찰형 리얼리티 STAY N과\r\n오프라인 팬들과 함께 만들어가는 무대 STAGE N\r\n두 개의 공간에서 이루어지는 K-POP 월간차트쇼 NAVER <NPOP>\r\n\r\nNPOP 스케줄\r\n📺 11/20(월) 8PM NPOP EP.12 (생방송)\r\n📺 11/22(수) 8PM NPOP EP.13\r\n📺 11/29(수) 8PM NPOP EP.14\r\n\r\n💙 NPOP 공식 채널 💙\r\nNaver: https://tv.naver.com/npop\r\nYouTube : https://www.youtube.com/@NPOP_OFFICIAL\r\nInstagram : https://www.instagram.com/npop_official/\r\nTwitter : https://twitter.com/NPOP_OFFICIAL'
        },
        'params': {
            'noplaylist': True,
        }
    }, {
        # https://now.naver.com/s/now.4759?shareReplayId=26331132#replay= now redirects to this url
        'url': 'https://now.naver.com/watch/MLrCxZEjX8zE',
        'md5': 'e05854162c21c221481de16b2944a0bc',
        'info_dict': {
            'id': 'MLrCxZEjX8zE',
            'title': '아이키X노제💖꽁냥꽁냥💖(1)',
            'ext': 'mp4',
            'thumbnail': r're:^https?://.*\.jpg',
            'timestamp': 1650369600,
            'upload_date': '20220419',
            'uploader_id': 'now.4759',
            'view_count': int,
            'uploader_url': 'https://now.naver.com/s/now.4759',
            'uploader': '아이키의 떰즈업',
            'duration': 3173,
            'like_count': 312,
            "description": '본: 화요일 밤 9시\r\n재: 본방 직후, 수-일 오전 11시, 오후 7시\r\n\r\n📺 다시보기 📺\r\n본방이 끝난 후 최신 에피소드는 \"NOW.앱 > 쇼 홈 > 에피소드 탭\" 에서 감상하세요!\r\nhttps://bit.ly/3Nw0PNQ\r\n\r\n아이키X노제\r\n우리 그냥 사랑하게 해주세요\r\n\r\n노제여보단 소리 질러~~!\r\n드디어 떰즈업에 강림한\r\n노제여보!\r\n\r\n아이키X노제\r\n투샷존버단 모두 다 모여라!\r\n\r\n✔️ 아이키X노제\r\n꽁냥꽁냥 연애의 밤?\r\n✔️ 강혜인X노지혜\r\n케미라는 것이 폭발한다🔥\r\n\r\n노제의 생애 첫 댄스는 과연 무엇?\r\n당신이 알던 노제,\r\n상상 그 이상의 매력을 보게 될 것!\r\n\r\n오늘도 꿀잼 보장\r\n엄지 손가락 들고\r\n함께해주실 거죠?👍\r\n\r\n구독과 알림 설정.\r\n떰즈로👍 업~~~ 해놓는 거다?'
        },
        'params': {
            'noplaylist': True,
        }
    }
    ]

    def _get_video_info_api_call_qs(self, api_url):
        import time
        import base64
        import hashlib
        import hmac

        # key from https://now.naver.com/_next/static/chunks/pages/_app-c8bbb02b32a20c3d.js (search for 'md=')
        key = b'nbxvs5nwNG9QKEWK0ADjYA4JZoujF4gHcIwvoCxFTPAeamq5eemvt5IWAYXxrbYM'

        msgpad = int(time.time() * 1000)
        # algorithm same as in yt_dlp/extractor/weverse.py::WeverseBaseIE._call_api
        md = base64.b64encode(hmac.HMAC(
            key, f'{api_url[:255]}{msgpad}'.encode(), digestmod=hashlib.sha1).digest()).decode()
        qs = parse_qs(f'msgpad={msgpad}&md={md}')
        return qs

    def _real_extract(self, url):
        video_id = self._match_id(url)
        qs = self._get_video_info_api_call_qs(api_url=f"{self._API_URL}/{video_id}")

        video_info_response = self._download_json(
            f'{self._API_URL}/{video_id}', video_id, query=qs,
            note=f'Downloading JSON video info for video id {video_id}')

        if not video_info_response:
            raise ExtractorError('Got unexpected or empty video info JSON response.', expected=True)

        video_info = traverse_obj(video_info_response, ('result', 'result'))
        if not video_info:
            raise ExtractorError('Got unexpected video info JSON data.', expected=True)

        video_clip_info = traverse_obj(video_info, 'clip')
        if not video_clip_info:
            raise ExtractorError('Could not find video clip info with Naver CDN video id in video info JSON.', expected=True)

        key = traverse_obj(video_info, ('play', 'inKey'))
        if not key:
            raise ExtractorError('Could not find API key in video info JSON.', expected=True)

        vid = traverse_obj(video_clip_info, 'videoId')
        if not vid:
            raise ExtractorError('Could not find Naver CDN video id in video clip info.', expected=True)

        info = self._extract_video_info(video_id, vid, key)

        info.update({
            'title': video_clip_info.get('title'),
            # episodeStartDateTime seems to be the start time for a live stream and registerDateTime the end time
            # registerDateTime seems to be the upload time for vods
            'upload_date': unified_strdate(dict_get(video_clip_info, ('episodeStartDateTime', 'registerDateTime'))),
            'timestamp': unified_timestamp(dict_get(video_clip_info, ('episodeStartDateTime', 'registerDateTime'))),
            # channelId and channelUrl in the video_clip_info are not always accurate
            'uploader_id': traverse_obj(video_info, ('channel', 'channelId')),
            'uploader_url': traverse_obj(video_info, ('channel', 'channelUrl')),
            'description': video_clip_info.get('description'),
            'duration': traverse_obj(video_clip_info, 'playTime'),
            'like_count': traverse_obj(video_clip_info, 'likeItCount')
        })
        return info
