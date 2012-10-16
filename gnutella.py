import os
import threading
import SocketServer
import socket

class TCPServerHandler(SocketServer.BaseRequestHandler):

	def setup(self):
		self._stop = False
		self.msgtracker = []
		self.sever_ip, self.server_port = self.server.server_address
		self.path = str(self.server_port)

	def getFiles(self):
		return os.listdir(self.path)

	def hasFile(self, thefile):
		files = self.getFiles()
		if thefile in files:
			return True
		else:
			return False

	def getNeighbors(self):
		thefile = open('%s/neighbors.txt' % (self.path), 'r')
		print '%s/neighbors.txt' % (self.path)
		items = thefile.readlines()
		thelist = []
		for item in items:
			#i = item.strip()
			#print '---%s---' % (i)
			#thelist.append(int(i))
			thelist.append(item)
		thefile.close()
		return thelist

	def handle(self):
		cmd = self.request.recv(1024).strip()
		if cmd.startswith('search'):
			items = cmd.split()
			command = items[0]
			msgID = items[1]
			thefile = items[2]
			ttl = int(items[3])
			msgtracker_dict = dict(self.msgtracker)
			if not msgtracker_dict.has_key(msgID):
				client_ip, client_port = self.client_address
				self.msgtracker.append((msgID, client_port))
				containlist = []
				if self.hasFile(thefile):
					containlist.append(self.server_port)
				if ttl-1 != 0:
					query = 'search %s %s %d' % (msgID, thefile, ttl-1)
					neighbors = self.getNeighbors()
					for neighbor in neighbors:
						sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						try:
							sock.connect(('localhost', int(neighbor.strip())))
							sock.sendall(query)
							receiver = sock.recv(1024)
							if receiver != 'NONE':
								containlist.extend(receiver)
						finally:
							sock.close()
				if len(containlist) == 0:
					self.request.sendall('NONE')
				else:
					self.request.sendall(containlist)
		elif cmd.startswith('download'):
			items = cmd.split()
			filename = items[1]
			thefile = open('%s/%s' % (self.path, filename), 'r')
			content = thefile.readlines()
			msg = ''
			for item in content:
				msg = msg + item + '\n'
			self.request.sendall(msg)
			thefile.close()

class ServerThread(threading.Thread):

	def __init__(self, port):
		threading.Thread.__init__(self)
		self._stopEvent = threading.Event()
		self.host = 'localhost'
		self.port = int(port)
		self.addr = (self.host, self.port)
		self.tcpServer = SocketServer.TCPServer(self.addr, TCPServerHandler)

	def run(self):
		while not self._stopEvent.isSet():
			self.tcpServer.serve_forever()
		self.tcpSever.shutdown()
	
	def join(self, timeout=None):
		self._stopEvent.set()
		threading.Thread.join(self, timeout)

class ClientThread(threading.Thread):

	def __init__(self, port):
		threading.Thread.__init__(self)
		self._stopEvent = threading.Event()
		self.port = port
		self.msgID = 0
	
	def getNeighbors(self):
		thefile = open('%s/neighbors.txt' % (self.port), 'r')
		items = thefile.readlines()
		thelist = []
		for item in items:
			thelist.append(int(item.strip()))
		thefile.close()
		return thelist

	def run(self):
		while not self._stopEvent.isSet():
			cmd = raw_input('Enter your command: ').strip()
			while cmd != 'shutdown':
				if cmd.startswith('search'):
					items = cmd.split()
					targetfile = items[1].strip()
					query = 'search %s%d %s 3' % (self.port, self.msgID, targetfile)
					self.msgID += 1
					containlist = []
					neighbors = self.getNeighbors()
					for neighbor in neighbors:
						sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						try:
							sock.connect(('localhost', neighbor))
							sock.sendall(query)
							receiver = sock.recv(1024)
							if receiver != 'NONE':
								containlist.extend(receiver)
						finally:
							sock.close()
					if len(containlist) == 0:
						print 'No such a file in network'
					else:
						print 'The file exists in ', containlist
				elif cmd.startswith('download'):
					items = cmd.split()
					targetport = int(items[2].strip())
					filename = items[1].strip()
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					try:
						sock.connect(('localhost', targetport))
						sock.sendall('download %s' % (filename))
						receiver = sock.recv(1024)
					finally:
						sock.close()
					thefile = open('%s/%s' % (self.port, filename), 'w')
					thefile.write(receiver)
					thefile.close()
				elif cmd == 'test':
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					sock.connect(('localhost', 3214))
					sock.sendall('Hello, World!')
					data = sock.recv(1024)
					sock.close()
					print 'Received', repr(data)
				
				cmd = raw_input('Enter your command: ').strip()
			if cmd == 'shutdown':
				self.join()

	def join(self, timeout=None):
		self._stopEvent.set()
		threading.Thread.join(self, timeout)

def main():
	port = raw_input('Enter the port will be used:').strip()
	serverThread = ServerThread(port)
	serverThread.start()
	clientThread = ClientThread(port)
	clientThread.start()

if __name__ == '__main__':
	main()
