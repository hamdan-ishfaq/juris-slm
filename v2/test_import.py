import logging
import sys
logging.basicConfig(level=logging.DEBUG)
try:
    from backend.src.main import app
    print('✓ App imported successfully')
    print(f'Routes registered: {len(app.routes)}')
    for route in app.routes[:10]:
        print(f'  - {route.path}')
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'✗ Error during import: {e}')
