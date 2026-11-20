"""Tatronics / CalibPro. Ejecución local: python run.py"""
import os
from app import create_app

mode = 'production' if os.environ.get('CALIBPRO_ENV') == 'production' else 'development'
app = create_app(mode)

if __name__ == '__main__':
    app.run(
        host=os.environ.get('CALIBPRO_HOST', '127.0.0.1'),
        port=int(os.environ.get('CALIBPRO_PORT', '5000')),
        debug=os.environ.get('CALIBPRO_DEBUG') == '1' and mode != 'production',
    )
