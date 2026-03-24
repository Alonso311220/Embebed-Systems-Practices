from http.server import BaseHTTPRequestHandler, HTTPServer

class WebServer(BaseHTTPRequestHandler):
	def do_GET(self):
		if self.path == '/':
			self.send_response(200)
			self.send_header("Content-type", "text/html")
			self.end_headers()
			self._serve_ui_file()
		else:
			self._serve_file(self.path[1:])

def  _serve_file(self, rel_path):
	if not os.path.isfile(rel_path):
		self.send_error(404)
		return
	self.send_response(200)
	mime = magic.Magic(mime=True)
	self.send_header("Content-type", mime.from_file(rel_path))
	self.end_headers()
	with open(rel_path, 'rb') as file:
		self.wfile.write(file.read())

def do_POST(self):
	content_length = int (self.headers.get('Content-Length'))
	if content_length < 1:
		return
	post_data = self.rfile.read(content_length)
	try:
		jobj = json.loads(post_data.decode("utf-8"))
		self._parse_post(jobj)
	except:
		print(sys.exc_info())
		print("Datos POST no reconocidos")	

def _parse_post(self, json_obj):
	if not 'action' in json_obj or not 'value' in json_obj:
		return
	switcher = {'led' : leds, 'marquee' : marquee, 'numpad' : bcd}
	if func: 
		print('\tCall{}({})'.format(func, json_obj['value']))
		func(json_obj['value'])
def main():
	webServer = HTTPServer(("192.168.1.254", 80), WebServer)
	print("Servidor iniciado")
	print("\tAtendiendo solicitudes entrantes")
	try:
		webServer.serve_forever()
	except KeyboardInterrupt:
		pass
	webServer.server_close()
	print("Server stopped.")

if __name__ == "__main__":
	main()
