import os
manual_test = os.environ.get('SCRUTINY_MANUAL_TEST', '0') == '1'
if ' ' not in os.environ and not manual_test:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
