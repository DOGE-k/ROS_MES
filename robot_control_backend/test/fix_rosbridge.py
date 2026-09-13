#!/usr/bin/env python3
import sys
import os

# Patch the OpenSSL.crypto module before importing twisted
try:
    from OpenSSL import crypto
    # Set the missing attribute if it doesn't exist
    if not hasattr(crypto.X509StoreFlags, 'NOTIFY_POLICY'):
        setattr(crypto.X509StoreFlags, 'NOTIFY_POLICY', 0)
    # Also patch the _lib if needed
    import cryptography.hazmat.bindings.openssl.binding as binding
    if not hasattr(binding.lib, 'X509_V_FLAG_NOTIFY_POLICY'):
        setattr(binding.lib, 'X509_V_FLAG_NOTIFY_POLICY', 0)
except Exception as e:
    print(f"Warning: Failed to patch OpenSSL: {e}", file=sys.stderr)

# Now import and run rosbridge_websocket
sys.path.insert(0, '/opt/ros/noetic/lib/rosbridge_server')
os.chdir('/opt/ros/noetic/lib/rosbridge_server')

# Execute the rosbridge_websocket script
exec(open('/opt/ros/noetic/lib/rosbridge_server/rosbridge_websocket').read())
