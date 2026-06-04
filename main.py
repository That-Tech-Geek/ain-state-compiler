import os
import json
import sys
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from ain_state_compiler.compiler.state_compiler import StateCompiler
from ain_state_compiler.compiler.token_optimizer import TokenOptimizer
from ain_state_compiler.sync import sync_from_hivemind
from ain_state_compiler.query import query_brain

# Configure project paths
PORT = 8000
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(PROJECT_DIR, "dashboard")

class AINHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default terminal logs for a cleaner output
        pass

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        # CORS preflight headers
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # ----------------------------------------------------
        # REST API Endpoints
        # ----------------------------------------------------
        compiler = StateCompiler(PROJECT_DIR)
        
        if path == "/api/raw-feeds":
            try:
                slack, jira, emails = compiler.load_data()
                self.send_json(200, {
                    "slack": slack,
                    "jira": jira,
                    "emails": emails
                })
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return
            
        elif path == "/api/state":
            try:
                state_json_path = os.path.join(PROJECT_DIR, "compiled_state", "operational_state.json")
                if not os.path.exists(state_json_path):
                    compiler.compile()
                with open(state_json_path, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                self.send_json(200, state_data)
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return
            
        elif path == "/api/metrics":
            try:
                metrics_path = os.path.join(PROJECT_DIR, "compiled_state", "token_optimization_metrics.json")
                if not os.path.exists(metrics_path):
                    compiler.compile()
                with open(metrics_path, "r", encoding="utf-8") as f:
                    metrics = json.load(f)
                self.send_json(200, metrics)
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return
            
        elif path == "/api/compile":
            try:
                # First sync from shared SQLite database
                sync_from_hivemind()
                summary = compiler.compile()
                self.send_json(200, {"status": "success", "summary": summary})
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return

        elif path == "/api/query":
            try:
                query = parse_qs(parsed_url.query)
                query_text = query.get("text", [""])[0]
                if not query_text:
                    self.send_json(400, {"error": "Query parameter 'text' is required."})
                    return
                ans, node, is_llm = query_brain(query_text)
                self.send_json(200, {
                    "query": query_text,
                    "answer": ans,
                    "node": node,
                    "is_llm": is_llm
                })
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return

        elif path == "/api/imm":
            # Serve specific IMM contents (e.g. ?name=product_deployment_imm)
            query = parse_qs(parsed_url.query)
            imm_name = query.get("name", ["product_deployment_imm"])[0]
            imm_path = os.path.join(PROJECT_DIR, "compiled_state", f"{imm_name}.md")
            if os.path.exists(imm_path):
                with open(imm_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_json(200, {"name": imm_name, "content": content})
            else:
                self.send_json(404, {"error": f"IMM {imm_name} not found."})
            return

        # ----------------------------------------------------
        # Static Dashboard Files
        # ----------------------------------------------------
        if path == "/" or path == "":
            file_to_serve = os.path.join(DASHBOARD_DIR, "index.html")
            content_type = "text/html"
        else:
            relative_path = path.lstrip("/")
            file_to_serve = os.path.join(DASHBOARD_DIR, relative_path)
            if path.endswith(".css"):
                content_type = "text/css"
            elif path.endswith(".js"):
                content_type = "application/javascript"
            else:
                content_type = "text/plain"

        # Serve static asset
        if os.path.exists(file_to_serve) and os.path.isfile(file_to_serve):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(file_to_serve, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # ----------------------------------------------------
        # Model Context Protocol (MCP) Handler / Simulation Endpoint
        # ----------------------------------------------------
        if path == "/mcp":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            
            try:
                mcp_request = json.loads(post_data)
                method = mcp_request.get("method")
                params = mcp_request.get("params", {})
                
                # Execute MCP Tools programmatically
                if method == "tools/list":
                    mcp_response = {
                        "tools": [
                            {
                                "name": "get_operational_state",
                                "description": "Retrieve the current compiled YAML operational state (OEG) showing truth matrices and conflicts.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {}
                                }
                            },
                            {
                                "name": "get_imm_module",
                                "description": "Get standard Markdown contents of an Institutional Memory Module (IMM) node.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "enum": ["product_deployment_imm", "acme_corp_billing_imm"]}
                                    },
                                    "required": ["name"]
                                }
                            }
                        ]
                    }
                    self.send_json(200, mcp_response)
                elif method == "tools/call":
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    
                    if tool_name == "get_operational_state":
                        yaml_path = os.path.join(PROJECT_DIR, "compiled_state", "operational_state.yaml")
                        if not os.path.exists(yaml_path):
                            StateCompiler(PROJECT_DIR).compile()
                        with open(yaml_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        self.send_json(200, {"content": [{"type": "text", "text": content}]})
                        
                    elif tool_name == "get_imm_module":
                        imm_name = arguments.get("name", "product_deployment_imm")
                        imm_path = os.path.join(PROJECT_DIR, "compiled_state", f"{imm_name}.md")
                        if os.path.exists(imm_path):
                            with open(imm_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            self.send_json(200, {"content": [{"type": "text", "text": content}]})
                        else:
                            self.send_json(404, {"error": f"IMM {imm_name} not found."})
                    else:
                        self.send_json(404, {"error": f"Tool {tool_name} not found."})
                else:
                    self.send_json(400, {"error": f"Method {method} not supported in MCP stub."})
            except Exception as e:
                self.send_json(500, {"error": f"MCP Parser Error: {str(e)}"})
            return
            
        self.send_json(404, {"error": "Endpoint not found"})

def run_server():
    # Make sure output directories and compile files exist on startup
    compiler = StateCompiler(PROJECT_DIR)
    print("[*] Performing G-Brain Startup Compilation...")
    compiler.compile()
    
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, AINHTTPRequestHandler)
    print(f"\n======================================================================")
    print(f"[*] AIN STATE COMPILER (G-BRAIN PROTOTYPE) SERVER ACTIVE")
    print(f"--> Local Dashboard: http://localhost:{PORT}/")
    print(f"--> MCP API Endpoint: http://localhost:{PORT}/mcp")
    print(f"======================================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[*] Shutting down AIN State Compiler server.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIN State Compiler Backend")
    parser.add_argument("--test", action="store_true", help="Run quick test suite and exit")
    args = parser.parse_args()
    
    if args.test:
        print("[*] Running AIN State Compiler test suite...")
        compiler = StateCompiler(PROJECT_DIR)
        summary = compiler.compile()
        print(f"[+] Test Ingest: {json.dumps(summary, indent=2)}")
        
        # Verify Token Optimization savings
        state_path = os.path.join(PROJECT_DIR, "compiled_state", "operational_state.json")
        with open(state_path, "r") as f:
            data = json.load(f)
        savings = TokenOptimizer.calculate_savings(data)
        print(f"[+] Token Optimization savings: {savings['saving_percentage']}% ({savings['saved_tokens']} tokens saved)")
        print("[+] Test validation completed successfully.")
        sys.exit(0)
        
    run_server()
