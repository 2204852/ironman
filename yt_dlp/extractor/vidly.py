from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    mimetype2ext,
    url_or_none,
)
from ..utils.traversal import traverse_obj


class VidlyIE(InfoExtractor):
    _VALID_URL = r'https?://(?:vid\.ly/|(?:s\.)?vid\.ly/embeded.html\?(?:[^#/]+&)?link=)(?P<id>\w+)'
    _EMBED_REGEX = [r'<script[^>]+\bsrc=[\'"](?P<url>(?:https?:)?//vid\.ly/\w+/embed[^\'"]+)',
                    r'<iframe[^>]+\bsrc=[\'"](?P<url>(?:https?:)?//(?:s\.)?vid\.ly/embeded.html\?(?:[^#/]+&)?link=\w+[^\'"]+)']
    _TESTS = [{
        # JWPlayer 7, Embeds forbidden
        'url': 'https://vid.ly/2i3o9j/embed',
        'info_dict': {
            'id': '2i3o9j',
            'ext': 'mp4',
            'title': '2i3o9j',
            'thumbnail': r're:https://\w+\.cloudfront\.net/',
        },
    }, {
        # JWPlayer 6
        'url': 'http://s.vid.ly/embeded.html?link=jw_test&new=1&autoplay=true&controls=true',
        'info_dict': {
            'id': 'jw_test',
            'ext': 'mp4',
            'title': '2x8m8t',
            'thumbnail': r're:https://\w+\.cloudfront\.net/',
        },
    }, {
        # Vidlyplayer
        'url': 'https://vid.ly/7x0e6l',
        'info_dict': {
            'id': '7x0e6l',
            'ext': 'mp4',
            'title': '7x0e6l',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)

        embed_script = self._download_webpage(
            f'https://vid.ly/{video_id}/embed', video_id, headers={'Referer': 'https://vid.ly/'})
        player = self._search_json(r'initCallback\(', embed_script, 'player', video_id)

        if player['player'].startswith('jwplayer'):
            return self._parse_jwplayer_data(player['config'], video_id)
        elif player['player'] == 'vidlyplayer':
            formats = []
            ext = mimetype2ext(traverse_obj(player, ('config', 'type')))
            if traverse_obj(player, ('config', 'source', {url_or_none})):
                formats.append({
                    'url': player['config']['source'],
                    'format_id': 'http-sd',
                    'ext': ext,
                })
            if traverse_obj(player, ('config', 'source_hd', {url_or_none})):
                formats.append({
                    'url': player['config']['source_hd'],
                    'format_id': 'http-hd',
                    'ext': ext,
                })
            # Has higher quality formats
            formats.extend(self._extract_m3u8_formats(
                f'https://d3fenhwk93s16g.cloudfront.net/{video_id}/hls.m3u8', video_id,
                fatal=False, note='Trying to guess m3u8 URL') or [])
            return {
                'id': video_id,
                'title': video_id,
                'formats': formats,
            }
        else:
            raise ExtractorError('Unknown player type')
