import cgi
import gzip
import random
import socketserver
import tempfile

from bs4 import BeautifulSoup
from google.cloud import language
from google.cloud.language import enums
from google.cloud.language import types
from pyicap import BaseICAPRequestHandler, ICAPServer
from string import Template

# Configuration
TEXT_CONTENT_TYPES = ['text/html'] 
ICAP_PORT = 13440
# As per https://cloud.google.com/natural-language/docs/categories
BLOCKED_CATEGORIES = {
    "/Adult": 0.7,
    "/Sports": 0.7
}
BLOCK_MESSAGE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" /><meta http-equiv="X-UA-Compatible" content="IE=edge" /><meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>403 - Access Denied</title>
    <style type="text/css">/*! normalize.css v5.0.0 | MIT License | github.com/necolas/normalize.css */html{font-family:sans-serif;line-height:1.15;-ms-text-size-adjust:100%;-webkit-text-size-adjust:100%}body{margin:0}article,aside,footer,header,nav,section{display:block}h1{font-size:2em;margin:.67em 0}figcaption,figure,main{display:block}figure{margin:1em 40px}hr{box-sizing:content-box;height:0;overflow:visible}pre{font-family:monospace,monospace;font-size:1em}a{background-color:transparent;-webkit-text-decoration-skip:objects}a:active,a:hover{outline-width:0}abbr[title]{border-bottom:none;text-decoration:underline;text-decoration:underline dotted}b,strong{font-weight:inherit}b,strong{font-weight:bolder}code,kbd,samp{font-family:monospace,monospace;font-size:1em}dfn{font-style:italic}mark{background-color:#ff0;color:#000}small{font-size:80%}sub,sup{font-size:75%;line-height:0;position:relative;vertical-align:baseline}sub{bottom:-.25em}sup{top:-.5em}audio,video{display:inline-block}audio:not([controls]){display:none;height:0}img{border-style:none}svg:not(:root){overflow:hidden}button,input,optgroup,select,textarea{font-family:sans-serif;font-size:100%;line-height:1.15;margin:0}button,input{overflow:visible}button,select{text-transform:none}[type=reset],[type=submit],button,html [type=button]{-webkit-appearance:button}[type=button]::-moz-focus-inner,[type=reset]::-moz-focus-inner,[type=submit]::-moz-focus-inner,button::-moz-focus-inner{border-style:none;padding:0}[type=button]:-moz-focusring,[type=reset]:-moz-focusring,[type=submit]:-moz-focusring,button:-moz-focusring{outline:1px dotted ButtonText}fieldset{border:1px solid silver;margin:0 2px;padding:.35em .625em .75em}legend{box-sizing:border-box;color:inherit;display:table;max-width:100%;padding:0;white-space:normal}progress{display:inline-block;vertical-align:baseline}textarea{overflow:auto}[type=checkbox],[type=radio]{box-sizing:border-box;padding:0}[type=number]::-webkit-inner-spin-button,[type=number]::-webkit-outer-spin-button{height:auto}[type=search]{-webkit-appearance:textfield;outline-offset:-2px}[type=search]::-webkit-search-cancel-button,[type=search]::-webkit-search-decoration{-webkit-appearance:none}::-webkit-file-upload-button{-webkit-appearance:button;font:inherit}details,menu{display:block}summary{display:list-item}canvas{display:inline-block}template{display:none}[hidden]{display:none}/*! Simple HttpErrorPages | MIT X11 License | https://github.com/AndiDittrich/HttpErrorPages */body,html{width:100%;height:100%;background-color:#21232a}body{color:#fff;text-align:center;text-shadow:0 2px 4px rgba(0,0,0,.5);padding:0;min-height:100%;-webkit-box-shadow:inset 0 0 100px rgba(0,0,0,.8);box-shadow:inset 0 0 100px rgba(0,0,0,.8);display:table;font-family:"Open Sans",Arial,sans-serif}h1{font-family:inherit;font-weight:500;line-height:1.1;color:inherit;font-size:36px}h1 small{font-size:68%;font-weight:400;line-height:1;color:#777}a{text-decoration:none;color:#fff;font-size:inherit;border-bottom:dotted 1px #707070}.lead{color:silver;font-size:21px;line-height:1.4}.cover{display:table-cell;vertical-align:middle;padding:0 20px}footer{position:fixed;width:100%;height:40px;left:0;bottom:0;color:#a0a0a0;font-size:14px}</style>
</head>
<body>
    <div class="cover"><h1>Access Denied <small>Error 403</small></h1><p class="lead">The requested resource has been blocked.</p>
    <p>${issues}</p></div>
    <footer><p>Technical Contact: <a href="mailto:x@example.com">x@example.com</a></p></footer>
</body>
</html>""")

def classify_text(text):
    """Classifies content categories of the provided text."""
    client = language.LanguageServiceClient()
    # Google's API has a limit of 128000 bytes, but that's for the size of the whole request so trim the data to first 65 kilobytes.
    limited = text[:65535]

    # Force language to be English, although this is suboptimal
    document = types.Document(
        content=limited.encode('utf-8'),
        language='en',
        type=enums.Document.Type.PLAIN_TEXT)

    categories = client.classify_text(document).categories
    return categories

def get_triggered(categories):
    """Returns any of the categories exceeding blocking threshold."""
    triggered = []
    for x in BLOCKED_CATEGORIES:
        for category in categories:
            if category.name.startswith(x) and category.confidence > BLOCKED_CATEGORIES[x]:
                triggered.append((category.name, category.confidence))
    return triggered

def extract_text(xs, encoding):
    """Extracts text from HTML."""
    soup = BeautifulSoup(xs, 'html.parser', from_encoding=encoding)
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

class ThreadingSimpleServer(socketserver.ThreadingMixIn, ICAPServer):
    pass

class ICAPHandler(BaseICAPRequestHandler):

    def conebam_OPTIONS(self):
        """Send options to the client. Disable previews."""
        self.set_icap_response(200)
        self.set_icap_header(b'Methods', b'RESPMOD')
        self.set_icap_header(b'Service', b'Conebam 1.0')
        self.set_icap_header(b'Preview', b'0')
        self.set_icap_header(b'Transfer-Preview', b'')
        self.set_icap_header(b'Transfer-Complete', b'*')
        self.set_icap_header(b'Transfer-Ignore', b'jpg,jpeg,gif,png,swf,flv,exe,mp4')
        self.send_headers(False)

    def read_req(self):
        """Reads request body, and returns the chunks."""
        b = []
        while True:
            chunk = self.read_chunk()
            if len(chunk)==0:
                break
            b.append(chunk)
        return b

    def is_filterable(self):
        """Determines whether the content type can likely be text classified."""
        result = False

        status = int(self.enc_res_status[1])
        value = self.enc_res_headers.get(b'content-type')
        
        # Don't react to other than 2xxs
        if status >= 200 and status <300 and value and len(value) > 0:
            for x in TEXT_CONTENT_TYPES:
                if str(value[0], 'utf-8').lower().find(x) != -1 :
                    result = True
        return result

    def get_charset(self):
        """Gets character set from content-type."""
        value = self.enc_res_headers.get(b'content-type')
        if value and len(value) > 0:
            _, params = cgi.parse_header(str(value[0], 'utf-8'))
            return params.get('charset')
        return None

    def get_decompressed(self, input):
        """ Attempt to decompress gzipped data. """
        value = self.enc_res_headers.get(b'content-encoding')
        if value and len(value) > 0 and value[0] == b'gzip':
            return gzip.decompress(input)
        return input

    def respond_blocked(self, triggered):
        """Sends a response for blocked page."""
        body = BLOCK_MESSAGE
        issues = ''
        if triggered:
            issues = 'Detected content types:<ul>' 
            for x in triggered:
                issues += '<li>' + str(x[0]) + ' with confidence ' + str(x[1]) + '</li>'
            issues += '</ul>'
        body = body.substitute(issues=issues).encode('utf-8')
        self.enc_req = None
        self.set_icap_response(200)
        self.set_enc_status(self.enc_res_status[0]+ b' 403 Forbidden')
        self.set_enc_header(b'Content-Type', b'text/html')
        self.set_enc_header(b'Content-Length', str(len(body)).encode('utf-8'))
        self.send_headers(has_body=True)
        if len(body) > 0:
            self.write_chunk(body)
        self.write_chunk(b'')

    def respond_original(self, xs):
        """Sends a response that is a copy of the original content."""
        self.set_icap_response(200)

        if self.enc_res_status is not None:
            self.set_enc_status(b' '.join(self.enc_res_status))
            for h in self.enc_res_headers:
                for v in self.enc_res_headers[h]:
                    self.set_enc_header(h, v)
        
        if not self.has_body:
            self.send_headers(False)
            self.log_request(200)
            return

        self.send_headers(True)
        for x in xs:
            self.write_chunk(x)
        self.write_chunk(b'')

    def conebam_RESPMOD(self):
        """Classifies content and filters it."""

        xs = self.read_req()

        if self.is_filterable():
            if xs and len(xs) > 0:
                data = b''.join(xs)
                xsu = self.get_decompressed(data)
                text = extract_text(xsu, self.get_charset())

                # Google's classifier expects at least 20 words
                wordcount = len(text.split())
                if wordcount > 20:
                    categories = classify_text(text)
                    triggered = get_triggered(categories)
                    if len(triggered) > 0:
                        self.respond_blocked(triggered)
                        return  

        # Respond with the original
        self.respond_original(xs)

server = ThreadingSimpleServer(('', ICAP_PORT), ICAPHandler)
try:
    while 1:
        server.handle_request()
except KeyboardInterrupt:
    print ("Finished")
