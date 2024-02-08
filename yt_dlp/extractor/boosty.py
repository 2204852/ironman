from .common import InfoExtractor
from .youtube import YoutubeIE
from ..utils import (
    ExtractorError,
    int_or_none,
    qualities,
    str_or_none,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class BoostyIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?boosty\.to/(?P<user>[^/#?]+)/posts/(?P<post_id>[^/#?]+)'
    _TESTS = [{
        # single ok_video
        'url': 'https://boosty.to/kuplinov/posts/e55d050c-e3bb-4873-a7db-ac7a49b40c38',
        'info_dict': {
            'id': 'd7473824-352e-48e2-ae53-d4aa39459968',
            'title': 'phasma_3',
            'channel': 'Kuplinov',
            'timestamp': 1655049000,
            'upload_date': '20220612',
            'modified_timestamp': 1668680993,
            'modified_date': '20221117',
            'tags': ['куплинов', 'phasmophobia'],
            'like_count': int,
            'ext': 'mp4',
            'duration': 105,
            'view_count': int,
            'thumbnail': r're:^https://i\.mycdn\.me/videoPreview\?',
        },
    }, {
        # multiple ok_video
        'url': 'https://boosty.to/maddyson/posts/0c652798-3b35-471f-8b48-a76a0b28736f',
        'info_dict': {
            'id': '0c652798-3b35-471f-8b48-a76a0b28736f',
            'title': 'то что не пропустил юта6',
            'channel': 'Илья Давыдов',
            'timestamp': 1694017040,
            'upload_date': '20230906',
            'modified_timestamp': 1694071178,
            'modified_date': '20230907',
            'tags': [],
            'like_count': int,
        },
        'playlist_count': 3,
        'playlist': [{
            'info_dict': {
                'id': 'cc325a9f-a563-41c6-bf47-516c1b506c9a',
                'title': 'то что не пропустил юта6',
                'ext': 'mp4',
                'duration': 31204,
                'view_count': int,
                'thumbnail': r're:^https://i\.mycdn\.me/videoPreview\?',
            },
        }, {
            'info_dict': {
                'id': 'd07b0a72-9493-4512-b54e-55ce468fd4b7',
                'title': 'то что не пропустил юта6',
                'ext': 'mp4',
                'duration': 25704,
                'view_count': int,
                'thumbnail': r're:^https://i\.mycdn\.me/videoPreview\?',
            },
        }, {
            'info_dict': {
                'id': '4a3bba32-78c8-422a-9432-2791aff60b42',
                'title': 'то что не пропустил юта6',
                'ext': 'mp4',
                'duration': 31867,
                'view_count': int,
                'thumbnail': r're:^https://i\.mycdn\.me/videoPreview\?',
            },
        }],
    }, {
        # single external video (youtube)
        'url': 'https://boosty.to/denischuzhoy/posts/6094a487-bcec-4cf8-a453-43313b463c38',
        'info_dict': {
            'id': 'EXelTnve5lY',
            'title': '4Класс',
            'channel': 'Денис Чужой',
            'timestamp': 1619380873,
            'upload_date': '20210425',
            'modified_timestamp': 1653321155,
            'modified_date': '20220523',
            'tags': [],
            'like_count': int,
            'ext': 'mp4',
            'duration': 816,
            'view_count': int,
            'thumbnail': r're:^https://i\.ytimg\.com/',
            # youtube fields
            'age_limit': 0,
            'availability': 'public',
            'categories': list,
            'channel_follower_count': int,
            'channel_id': 'UCCzVNbWZfYpBfyofCCUD_0w',
            'channel_is_verified': bool,
            'channel_url': r're:^https://www\.youtube\.com/',
            'comment_count': int,
            'description': str,
            'heatmap': 'count:100',
            'live_status': str,
            'playable_in_embed': bool,
            'uploader': str,
            'uploader_id': str,
            'uploader_url': r're:^https://www\.youtube\.com/',
        },
    }]

    def _real_extract(self, url):
        user, post_id = self._match_valid_url(url).group('user', 'post_id')
        post = self._download_json(
            f'https://api.boosty.to/v1/blog/{user}/post/{post_id}', post_id,
            note='Downloading post data', errnote='Unable to download post data')

        post_title = post.get('title')
        if not post_title:
            self.report_warning('Unable to extract post title. Falling back to parsing html page')
            webpage = self._download_webpage(url, video_id=post_id)
            post_title = (self._og_search_title(webpage, fatal=False)
                          or self._html_extract_title(webpage, fatal=True))

        common_metadata = {
            'title': post_title,
            **traverse_obj(post, {
                'channel': ('user', 'name', {str}),
                'channel_id': ('user', 'id', {str_or_none}),
                'timestamp': ('createdAt', {int_or_none}),
                'release_date': ('publishTime', {int_or_none}),
                'modified_timestamp': ('updatedAt', {int_or_none}),
                'tags': ('tags', ..., 'title', {str}),
                'like_count': ('count', 'likes', {int_or_none}),
            }),
        }
        entries = []
        for item in traverse_obj(post, ('data', ..., {dict})):
            item_type = item.get('type')
            if item_type == 'video' and url_or_none(item.get('url')):
                entries.append(self.url_result(item['url'], YoutubeIE))
            elif item_type == 'ok_video':
                video_id = item.get('id') or post_id
                entries.append({
                    'id': video_id,
                    'formats': self._extract_formats(item.get('playerUrls'), video_id),
                    **common_metadata,
                    **traverse_obj(item, {
                        'title': ('title', {str}),
                        'duration': ('duration', {int_or_none}),
                        'view_count': ('viewCounter', {int_or_none}),
                        'thumbnail': (('previewUrl', 'defaultPreview'), {url_or_none}),
                    }, get_all=False)})

        if not entries:
            raise ExtractorError('No videos found', expected=True)
        if len(entries) == 1:
            return entries[0]
        return self.playlist_result(entries, post_id, post_title, **common_metadata)

    def _extract_formats(self, player_urls, video_id):
        formats = []
        mp4_types = ('tiny', 'lowest', 'low', 'medium', 'high', 'full_hd', 'quad_hd', 'ultra_hd')
        quality = qualities(mp4_types)
        for player_url in traverse_obj(player_urls, lambda _, v: url_or_none(v['url'])):
            url = player_url['url']
            format_type = player_url.get('type')
            if format_type in ('hls', 'hls_live', 'live_ondemand_hls', 'live_playback_hls'):
                formats.extend(self._extract_m3u8_formats(url, video_id, m3u8_id='hls', fatal=False))
            elif format_type in ('dash', 'dash_live', 'live_playback_dash'):
                formats.extend(self._extract_mpd_formats(url, video_id, mpd_id='dash', fatal=False))
            elif format_type in mp4_types:
                formats.append({
                    'url': url,
                    'ext': 'mp4',
                    'format_id': format_type,
                    'quality': quality(format_type),
                })
            else:
                self.report_warning(f'Unknown format type: {format_type!r}')
        return formats
