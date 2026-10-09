"""无网络 URL 凭证检查；敏感请求拒绝，日志去掉用户信息、query 与 fragment。"""
import re
from urllib.parse import urlsplit, unquote, parse_qsl, urlunsplit

def decoded(value):
    for _ in range(5):
        nxt=unquote(value)
        if nxt==value:return value
        value=nxt
    if '%' in value:raise ValueError('AMBIGUOUS_URL_ENCODING')
    return value

def assert_no_credentials(url, depth=0):
    if depth>5:raise ValueError('NESTED_URL_LIMIT')
    p=urlsplit(url)
    if p.username is not None or p.password is not None:raise ValueError('URL_CREDENTIALS_NOT_ALLOWED')
    for key,value in parse_qsl(p.query,keep_blank_values=True,max_num_fields=100):
        normalized=re.sub(r'[^a-z0-9]', '', decoded(key).casefold())
        if normalized in {'token','accesstoken','refreshtoken','idtoken','authtoken','password','passwd','pwd','secret','clientsecret','apikey','authorization','auth','credential','credentials','accesskey','awsaccesskeyid','sessionid','signature','xamzsignature','xamzcredential','xamzsecuritytoken'}:
            raise ValueError('CREDENTIAL_QUERY_NOT_ALLOWED')
        nested=decoded(value)
        if nested.startswith(('https://','http://')):
            assert_no_credentials(nested,depth+1)

def safe_url_for_log(url):
    try:
        p=urlsplit(url)
        return urlunsplit((p.scheme,p.hostname or '',p.path,'',''))
    except ValueError:return '[INVALID_URL]'
