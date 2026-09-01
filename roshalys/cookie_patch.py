import http.cookies as _http_cookies


def _patch_morsel_output():
    _orig = _http_cookies.Morsel.output

    def _fixed_output(self, attrs=None, header="Set-Cookie:"):
        if header:
            return _orig(self, attrs=attrs, header=header)
        return self.OutputString(attrs)

    if getattr(_http_cookies.Morsel, "__roshalys_patched", False):
        return
    _http_cookies.Morsel.output = _fixed_output
    _http_cookies.Morsel.__roshalys_patched = True


_patch_morsel_output()
