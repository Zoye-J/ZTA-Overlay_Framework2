#!/usr/bin/env python
"""Complete startup script for ZTA Overlay Network with PROPER SSL"""
import subprocess
import time
import os
import sys
import threading
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
processes = []

def run_controller():
    print("🔐 Starting ZTA Controller (HTTPS)...")
    return subprocess.Popen(
        [sys.executable, 'controller/app.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def run_edge_router():
    print("🔐 Starting Edge Router (HTTPS with cert validation)...")
    return subprocess.Popen(
        [sys.executable, 'edge-router/simple_router.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def run_gateway():
    print("🔐 Starting Gateway Service (HTTPS with mTLS)...")
    return subprocess.Popen(
        [sys.executable, 'services/gateway/app.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def run_api_server():
    print("🔐 Starting API Server (HTTPS)...")
    return subprocess.Popen(
        [sys.executable, 'services/api_server/app.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def print_output(process, name):
    for line in process.stdout:
        if line.strip():
            print(f"[{name}] {line.strip()}")

def signal_handler(sig, frame):
    print("\n\n🛑 Shutting down ZTA Overlay Network...")
    for p in processes:
        try:
            p.terminate()
        except:
            pass
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("🇧🇩 ZTA Overlay Network - Zero Trust Architecture")
    print("=" * 60)
    print("\nArchitecture Features:")
    print("  ✅ All services bound to localhost only")
    print("  ✅ No inbound ports exposed")
    print("  ✅ HTTPS with TLS 1.2+ only")
    print("  ✅ Edge Router with certificate validation")
    print("  ✅ Bangladesh context (clearance levels, departments)")
    print("\nStarting components...\n")
    
    # Verify certificates exist
    certs_dir = os.path.join(BASE_DIR, 'certs')
    required_certs = [
        'ca.crt', 'ca.key',
        'identities/controller/controller.crt', 'identities/controller/controller.key',
        'identities/gateway/gateway.crt', 'identities/gateway/gateway.key',
        'identities/api-server/api-server.crt', 'identities/api-server/api-server.key'
    ]
    
    missing_certs = []
    for cert in required_certs:
        if not os.path.exists(os.path.join(certs_dir, cert)):
            missing_certs.append(cert)
    
    if missing_certs:
        print("❌ Missing certificates:")
        for cert in missing_certs:
            print(f"   - {cert}")
        print("\nPlease run: python certs/generate_identities.py")
        sys.exit(1)
    
    print("✅ All certificates found\n")
    
    # Start all components
    processes.append(run_controller())
    time.sleep(2)
    
    processes.append(run_edge_router())
    time.sleep(1)
    
    processes.append(run_gateway())
    time.sleep(1)
    
    processes.append(run_api_server())
    
    print("\n" + "=" * 60)
    print("✅ ZTA Overlay Network is RUNNING with PROPER SSL!")
    print("=" * 60)
    print("\n🌐 Access Points (HTTPS only):")
    print("  • Edge Router: https://localhost:9999")
    print("  • Gateway: https://localhost:5000")
    print("  • API Server: https://localhost:5001")
    print("  • Controller: https://localhost:8080")
    print("\n🔒 Security Features Active:")
    print("  • TLS 1.2+ only (no downgrade)")
    print("  • Certificate validation enabled")
    print("  • No HTTP endpoints exposed")
    print("  • All services require proper certificates")
    print("\n📋 Test Login:")
    print("  • intelligence_officer / password123 (TOP_SECRET)")
    print("\n⚠️  Note: Self-signed certificates - accept browser warning")
    print("\nPress Ctrl+C to stop all services\n")
    
    # Monitor all processes
    threads = []
    names = ["Controller", "Edge Router", "Gateway", "API Server"]
    for i, p in enumerate(processes):
        name = names[i] if i < len(names) else f"Process-{i}"
        t = threading.Thread(target=print_output, args=(p, name))
        t.daemon = True
        t.start()
        threads.append(t)
    
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)