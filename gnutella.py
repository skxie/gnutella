import os
import threading
import SocketServer
import socket
import time

class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):

	def setup(self):
		self._stop = False
		self.server_ip, self.server_port = self.server.server_address
		self.client_ip, self.client_port = self.client_address
		self.path = str(self.server_port)


	def handle(self):
		cmd = self.request.recv(1024).strip()
		#handle the issued query to find a specific file
		if cmd.startswith('search'):
			items = cmd.split()
			command = items[0]
			msgID = items[1]
			thefile = items[2]
			ttl = int(items[3])
			self.search_handle(command, msgID, thefile, ttl)
		#handle download request
		elif cmd.startswith('download'):
			items = cmd.split()
			filename = items[1]
			if self.hasFile(self.path, filename):
				thefile = open('%s/%s' % (self.path, filename), 'r')
			elif self.hasFile('%s/downloads' % (self.path), filename):
				thefile = open('%s/downloads/%s' % (self.path, filename), 'r')
			content = thefile.readlines()
			msg = ''
			for item in content:
				msg = msg + item + '\n'
			self.request.sendall(msg)
			thefile.close()
		#return the property of a file
		elif cmd.startswith('fileprop'):
			items = cmd.split()
			filename = items[1]
			fileprop = self.getFileProp(filename)
			self.request.sendall(fileprop)
		#return version number of a file
		elif cmd.startswith('pullcheck'):
			items = cmd.split()
			filename = items[1]
			fileprop = self.getFileProp(filename)
			item = fileprop.split()
			self.request.sendall(item[1])
		#handle invalidate request
		elif cmd.startswith('invalidate'):
			items = cmd.split()
			thefile = items[1]
			ttl = int(items[2])
			#check whether the file is downloaded into this peer
			path = '%s/downloads' % (self.path)
			if self.hasFile(path, thefile):
				self.delFile(path, thefile)
			#propagate the invalidate request
			if ttl-1 != 0:
				neighbors = self.getNeighbors()
				for neighbor in neighbors:
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					sock.connect(('localhost', int(neighbor.strip())))
					sock.sendall('invalidate %s %d' % (thefile, ttl-1))
					sock.close()

	def search_handle(self, command, msgID, thefile, ttl):
		if not self.has_msg(msgID):
			self.add_msg(msgID)
			containlist = ''
			#find whether the file is in this peer
			if self.hasFile(self.path, thefile) or self.hasFile('%s/downloads' % (self.path), thefile):
				if containlist == '':
					containlist = '%s' % (self.server_port)
				else:
					containlist += ' and %s' % (self.server_port)
			#broadcast the query to all the neighbors
			if ttl-1 != 0:
				query = 'search %s %s %d' % (msgID, thefile, ttl-1)
				print query
				neighbors = self.getNeighbors()
				for neighbor in neighbors:
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					sock.connect(('localhost', int(neighbor.strip())))
					sock.sendall(query)
					#combine all the peers contain the specific file
					receiver = sock.recv(1024)
					if receiver != 'NONE':
						if containlist == '':
							containlist = receiver
						else:
							containlist += ' and %s' % (reciever)
					sock.close()
			if containlist == '':
				self.request.sendall('NONE')
			else:
				self.request.sendall(containlist)
		#already checked
		else:
			self.request.sendall('NONE')
	
	#get the property of a file, e.g., version number, origin server, TTR
	def getFileProp(self, filename):
		thefile = open('%s/fileprop.txt' % (self.path), 'r')
		items = thefile.readlines()
		for item in items:
			if item.startswith(filename):
				thefile.close()
				return item
		thefile.close()

	#track the query
	def add_msg(self, msgID):
		thefile = open('%s/msgtracker.txt' % (self.path), 'a')
		thefile.write('%s:%s\n' % (msgID, self.client_port))
		thefile.close()

	#determine whether the query was processed in this peer
	def has_msg(self, msgID):
		thefile = open('%s/msgtracker.txt' % (self.path), 'r')
		items = thefile.readlines()
		for item in items:
			if item.startswith(msgID):
				thefile.close()
				return True
		thefile.close()
		return False

	#check whether a specific file exists in this peer
	def hasFile(self, path, thefile):
		files = os.listdir(path)
		if thefile in files:
			return True
		else:
			return False
	
	#discard a outdated file from this peer
	def delFile(self, path, thefile):
		os.remove('%s/%s' % (path, thefile))
		print 'The file %s is invalidate and was deleted' % (thefile)

	#obtain all the neighbors from the neighbor list
	def getNeighbors(self):
		thefile = open('%s/neighbors.txt' % (self.path), 'r')
		print '%s/neighbors.txt' % (self.path)
		items = thefile.readlines()
		thelist = []
		for item in items:
			thelist.append(item)
		thefile.close()
		return thelist
	
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	pass

class ServerThread(threading.Thread):

	def __init__(self, port):
		threading.Thread.__init__(self)
		self.host = 'localhost'
		self.port = int(port)
		self.addr = (self.host, self.port)
		self.tcpSever = ThreadedTCPServer(self.addr, ThreadedTCPRequestHandler)

	def run(self):
		#for each request, a new thread is issued to handle
		handler_thread = threading.Thread(target=self.tcpSever.serve_forever)
		handler_thread.start()

#pull check
class PullCheckThread(threading.Thread):

	def __init__(self, port, filename):
		threading.Thread.__init__(self)
		self.path = port
		self.filename = filename

	def run(self):
		while True:
			#obtain the property first
			prop = ''
			thefile = open('%s/fileprop.txt' % (self.path), 'r')
			items = thefile.readlines()
			for item in items:
				if item.startswith(self.filename):
					prop = item.strip()
					break
			i = prop.split()
			version_number = int(i[1])
			port = int(i[2])
			ttr = int(i[3])
			#periodically check
			time.sleep(ttr)
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.connect(('localhost', port))
			sock.sendall('pullcheck %s' % (self.filename))
			receiver = sock.recv(1024)
			sock.close()
			#compare version number
			if (int(receiver) > version_number):
				print 'The file %s is outdated' % (self.filename)

class ClientThread(threading.Thread):

	def __init__(self, port):
		threading.Thread.__init__(self)
		self.port = port
		self.msgID = 0
		
	def run(self):
		print '''
		Hi, this is p2p system which provides the following function:
		1. search. search the specific file to check whether it is shared in the system.
		2. download. download a particular file from a specific peer.
		3. invalidate. broadcast to other peers which hold a particular stale file.
		'''
		cmd = raw_input('Enter your command: ').strip()
		while cmd != 'shutdown':
			#issue a query request to search whether a file exists in the p2p file sharing system
			if cmd.startswith('search'):
				items = cmd.split()
				targetfile = items[1].strip()
				#create a query with msgID and ttl
				query = 'search %s%d %s 3' % (self.port, self.msgID, targetfile)
				self.msgID += 1
				containlist = ''
				neighbors = self.getNeighbors()
				#broadcast the query to all the neighbors to find the specific file
				for neighbor in neighbors:
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					sock.connect(('localhost', neighbor))
					sock.sendall(query)
					receiver = sock.recv(1024)
					#obtain the list of peers which have such an issued file
					if receiver != 'NONE':
						if containlist == '':
							containlist = receiver
						else:
							containlist += ' and %s' % (receiver)
					sock.close()
				if containlist == '':
					print 'No such a file in network'
				else:
					print 'The file exists in ', containlist
			#download a specific file from a peer
			elif cmd.startswith('download'):
				items = cmd.split()
				targetport = int(items[2].strip())
				filename = items[1].strip()
				#update the proporty of a file
				sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				sock.connect(('localhost', targetport))
				sock.sendall('fileprop %s' % (filename))
				receiver = sock.recv(1024)
				self.updateFileProp(receiver, filename)
				sock.close()
				#download the file
				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				s.connect(('localhost', targetport))
				s.sendall('download %s' % (filename))
				receiver = ''
				receiver = s.recv(1024)
				s.close()
				thefile = open('%s/downloads/%s' % (self.port, filename), 'w')
				thefile.write(receiver)
				thefile.close()
				print 'The file %s was downloaded' % (filename)
				#a new thread periodically pull check the file
				pullCheckThread = PullCheckThread(self.port, filename)
				pullCheckThread.start()
			#invalidate a outdated file in a push approach
			elif cmd.startswith('invalidate'):
				neighbors = self.getNeighbors()
				for neighbor in neighbors:
					sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					sock.connect(('localhost', neighbor))
					sock.sendall('%s 3' % (cmd))
					sock.close()
			cmd = raw_input('Enter your command: ').strip()

	#update the property of a file after download it
	def updateFileProp(self, fileprop, filename):
		content = ''
		thefile = open('%s/fileprop.txt' % (self.port), 'r')
		items = thefile.readlines()
		for item in items:
			if not item.startswith(filename):
				content += item
		content += fileprop
		thefile.close()
		thefile = open('%s/fileprop.txt' % (self.port), 'w')
		thefile.write(content)
		thefile.close()

	#obtain all the neighbors from the neighbor list
	def getNeighbors(self):
		thefile = open('%s/neighbors.txt' % (self.port), 'r')
		items = thefile.readlines()
		thelist = []
		for item in items:
			thelist.append(int(item.strip()))
		thefile.close()
		return thelist

def main():
	port = raw_input('Enter the port will be used:').strip()
	#start a sever thread to handle reqeusts
	serverThread = ServerThread(port)
	serverThread.start()
	#start a client to issue requests
	clientThread = ClientThread(port)
	clientThread.start()

if __name__ == '__main__':
	main()
