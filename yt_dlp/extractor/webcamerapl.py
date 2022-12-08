import codecs

from .common import InfoExtractor


class WebcameraplIE(InfoExtractor):
    _VALID_URL = r'https?://(?P<id>[\w-]+)\.webcamera\.pl'
    _TESTS = [{
        'url': 'https://warszawa-plac-zamkowy.webcamera.pl',
        'info_dict': {
            'id': 'warszawa-plac-zamkowy',
            'ext': 'mp4',
            'title': 'WIDOK NA PLAC ZAMKOWY W WARSZAWIE',
        }
    }, {
        'url': 'https://gdansk-stare-miasto.webcamera.pl/',
        'info_dict': {
            'id': 'gdansk-stare-miasto',
            'ext': 'mp4',
            'title': 'GDAŃSK - widok na Stare Miasto',
        }
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        rot13_m3u8_url = self._search_regex(r'data-src\s*=\s*"(uggc[^"]+\.z3h8)"',
                                            webpage, 'm3u8 url', default=None)
        if not rot13_m3u8_url:
            self.raise_no_formats('No video/audio found at the provided url', expected=True)

        m3u8_url = codecs.decode(rot13_m3u8_url, 'rot-13')
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(m3u8_url, video_id, live=True)

        return {
            'id': video_id,
            'title': self._html_search_regex(r'<h1\b[^>]*>([^>]+)</h1>', webpage, 'title'),
            'formats': formats,
            'subtitles': subtitles,
            'is_live': True,
        }
