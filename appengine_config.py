from google.appengine.ext import vendor
import sys
import os
# Add any libraries installed in the "lib" folder.
print("will add lib")
vendor.add('lib')
print('added lib')
vendor.add(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib'))
print('added abs path to lib')
sys.path = ['lib'] + sys.path
