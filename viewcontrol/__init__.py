from flask import Flask
from config import Config
from viewcontrol import show

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    app.meineshow = show.Show(app.config['SHOWFOLDER'])

    from viewcontrol.frontend import bp as frontend_bp
    app.register_blueprint(frontend_bp)

    return app