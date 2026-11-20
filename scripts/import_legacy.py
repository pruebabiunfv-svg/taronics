"""Importa la base existente y las fotos a instance/ antes del primer arranque.

Requiere la carpeta migration incluida en el paquete; nunca sobrescribe DB.
Ejecutar con la aplicación detenida. Verificar qué datos contienen las cuentas previas.
"""
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'migration' / 'calibpro_original.db'
DST = Path(os.getenv('DATABASE_PATH', str(ROOT / 'instance' / 'calibpro.db')))
PHOTOS_DST = Path(os.getenv('UPLOAD_FOLDER', str(ROOT / 'instance' / 'uploads' / 'photos')))


def main():
    if not SRC.exists():
        raise SystemExit('No se encuentra migration/calibpro_original.db.')
    if DST.exists():
        raise SystemExit(f'Destino existente: {DST}. No se ha sobrescrito ningún dato.')
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, DST)
    PHOTOS_DST.mkdir(parents=True, exist_ok=True)
    n = 0
    for image in (ROOT / 'migration' / 'uploads' / 'photos').glob('*'):
        if image.is_file() and not (PHOTOS_DST / image.name).exists():
            shutil.copy2(image, PHOTOS_DST / image.name)
            n += 1
    print(f'Base previa copiada en: {DST}. Fotos restauradas: {n}.')
    print('ATENCIÓN: revisar usuarios existentes y sustituir credenciales antiguas antes de producción.')


if __name__ == '__main__':
    main()
