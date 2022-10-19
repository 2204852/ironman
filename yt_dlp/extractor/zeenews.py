from .common import InfoExtractor
from ..utils import unified_strdate


class ZeeNewsIE(InfoExtractor):
    _VALID_URL = r'https?://zeenews\.india\.com/[^#?]+/video/(?P<display_id>[^#/?]+)/(?P<id>\d+)'
    _TESTS = [
        {
            'url': 'https://zeenews.india.com/hindi/india/delhi-ncr-haryana/delhi-ncr/video/greater-noida-video-viral-on-social-media-attackers-beat-businessman-and-his-son-oppose-market-closed-atdnh/1402138',
            'info_dict': {
                'id': '1402138',
                'description': 'md5:d9cbfcfb906666241e3659ebfe775e65',
                'ext': 'mp4',
                'title': 'Greater Noida Video: हमलावरों ने दिनदहाड़े दुकान में घुसकर की मारपीट, देखें वीडियो',
                'display_id': 'greater-noida-video-viral-on-social-media-attackers-beat-businessman-and-his-son-oppose-market-closed-atdnh',
                'upload_date': '20221019',
                'thumbnail': r're:^https?://.*\.jpg*',
            }
        },
        {
            'url': 'https://zeenews.india.com/hindi/india/video/videsh-superfast-queen-elizabeth-iis-funeral-today/1357710',
            'info_dict': {
                'id': '1357710',
                'description': 'md5:7ccad8abce3d1ffb00074ef2f05212b8',
                'ext': 'mp4',
                'title': 'Videsh Superfast: महारानी के अंतिम संस्कार की तैयारी शुरू',
                'display_id': 'videsh-superfast-queen-elizabeth-iis-funeral-today',
                'upload_date': '20220919',
                'thumbnail': r're:^https?://.*\.jpg*',
            }
        }
    ]

    def _real_extract(self, url):
        match = self._match_valid_url(url).groupdict()
        content_id, display_id = match['id'], match['display_id']
        webpage = self._download_webpage(url, content_id)
        json_ld_list = list(self._yield_json_ld(webpage, display_id))
        info = next(json_ld for json_ld in json_ld_list if json_ld.get('@type') == 'VideoObject')

        formats = self._extract_m3u8_formats(info.get('embedUrl'), content_id, 'mp4')
        self._sort_formats(formats)

        return {
            'id': content_id,
            'description': info.get('description'),
            'title': info.get('name'),
            'display_id': display_id,
            'formats': formats,
            'upload_date': unified_strdate(info.get('uploadDate')),
            'thumbnail': info.get('thumbnailUrl'),
        }
