"""Loopback-only local server. Vercel imports api/*.py directly."""
from .server import app
if __name__=='__main__':
    app.run(host='127.0.0.1',port=5328,debug=False,use_reloader=False,threaded=True)
