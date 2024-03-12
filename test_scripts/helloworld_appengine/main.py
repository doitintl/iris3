from flask import Flask


app = Flask(__name__)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return 'You want path: %s' % path

@app.errorhandler(404)
def handle_404(e):
    # handle all other routes here
    return f'Not Found {e}, but we HANDLED IT'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
