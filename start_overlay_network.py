#start_overlay_network.py
"""Complete startup script for ZTA Overlay Network"""
import subprocess
import time
import os
import sys
import threading
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
processes = []

def run_controller():
    """Start the controller"""
    print("🚀 Starting ZTA Controller...")
    return subprocess.Popen(
        [sys.executable, 'controller/app.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def run_edge_router():
    """Start the edge router"""
    print("🌐 Starting Edge Router...")
    return subprocess.Popen(
        [sys.executable, 'edge-router/simple_router.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def run_gateway():
    """Start the gateway service"""
    print("🚪 Starting Gateway Service...")
    return subprocess.Popen(
        [sys.executable, 'services/gateway/app.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def run_api_server():
    """Start the API server"""
    print("📡 Starting API Server...")
    return subprocess.Popen(
        [sys.executable, 'services/api_server/app.py'],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def print_output(process, name):
    """Print process output"""
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
    print("  ✅ Overlay network proxy")
    print("  ✅ Centralized policy controller")
    print("  ✅ Bangladesh context (clearance levels, departments)")
    print("\nStarting components...\n")
    
    # # Setup sample data
    # print("📦 Setting up sample data...")
    # try:
    #     subprocess.run([sys.executable, 'scripts/setup_sample_data.py'], cwd=BASE_DIR, check=True)
    #     print()
    # except subprocess.CalledProcessError as e:
    #     print(f"Warning: Sample data setup had issues: {e}")
    #     print()
    
    # Wait a bit for database to be ready
    time.sleep(1)
    
    # Start all components
    processes.append(run_controller())
    time.sleep(2)
    
    processes.append(run_edge_router())
    time.sleep(1)
    
    processes.append(run_gateway())
    time.sleep(1)
    
    processes.append(run_api_server())
    
    print("\n Access Points:")
    print("  • Main Dashboard: https://localhost:5000")
    print("  • Controller API: http://localhost:8080 (HTTP)")
    print("  • Edge Router Proxy: https://localhost:9999")
    print("\n⚠️  IMPORTANT: Accept the self-signed certificate warning in your browser")
    
    # Monitor all processes
    threads = []
    for i, p in enumerate(processes):
        names = ["Controller", "Edge Router", "Gateway", "API Server"]
        name = names[i] if i < len(names) else f"Process-{i}"
        t = threading.Thread(target=print_output, args=(p, name))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Keep main thread alive
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)