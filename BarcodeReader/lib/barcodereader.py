# -*- coding: utf-8 -*-
##########################################################
# Cause we need some more services !
# Aldebaran Robotics (c) 2014 All Rights Reserved -
##########################################################

__version__ = "0.0.1"
__copyright__ = "Copyright 2016, Aldebaran Robotics"

import sys
import functools

import qi
import zbar
import Image
import vision_definitions


"""BarcodeReader

Class implementing NAOqi service named BarcodeReader.
"""
class BarcodeReader:
	def __init__(self, session):
		self.session = session
		self.serviceName = self.__class__.__name__
		self.logger = qi.Logger(self.serviceName)

		self.scanning = False
		self.scanner = zbar.ImageScanner()

		self._connect_services() # Init services
		self._set_parameters() # Set parameters
		self._create_signals() # Init Signals

		self.logger.info("Ready!")

	def _connect_services(self):
		"""Connect to all services required by BarcodeReader"""
		self.logger.info('Connecting services...')
		self.services_connected = qi.Promise()
		services_connected_fut = self.services_connected.future()

		def get_services():
			"""Attempt to get all services"""
			try:
				self.mem = self.session.service('ALMemory')
				self.vid = self.session.service("ALVideoDevice")
				self.logger.info('All services are now connected')
				self.services_connected.setValue(True)
			except RuntimeError as e:
				self.logger.warning('Missing service:\n {}'.format(e))

		get_services_task = qi.PeriodicTask()
		get_services_task.setCallback(get_services)
		get_services_task.setUsPeriod(int(2*1000000))  # check every 2s
		get_services_task.start(True)
		try:
			services_connected_fut.value(30*1000)  # timeout = 30s
			get_services_task.stop()
		except RuntimeError:
			get_services_task.stop()
			self.logger.error('Failed to reach all services after 30 seconds.')
			raise RuntimeError

	def _set_parameters(self):
		self.logger.info('Setting parameters...')

		# We're doing here a little cleaning
		subscribers = self.vid.getSubscribers()
		for sub in subscribers:
			if "BarcodeReader_python_client" in sub:
				self.vid.unsubscribe(sub)
			elif "videoBuffer" in sub:
				self.vid.unsubscribe(sub)

		# Register a Video Module
		resolution = vision_definitions.kVGA # Image of 640*480px
		colorSpace = vision_definitions.kRGBColorSpace
		fps = 5
		self.videoClient = self.vid.subscribe("BarcodeReader_python_client", resolution, colorSpace, fps)
		self.vid.setParam(40, 1) # force auto focus
		self.logger.info('Parameters have been set...')

	def _create_signals(self):
		self.logger.info('Creating required signals and events...')
		self.onBarcodeDetected = qi.Signal()
		# self.onBarcodeDetectedEvent = '{}/{}'.format(self.serviceName, 'BarcodeDetected')
		# self.mem.declareEvent(self.onBarcodeDetectedEvent, self.serviceName)
		self.logger.info('All signals have been created')

	def _connect_signals(self):
		self.logger.info('Binding signals and events...')
		# self.conID = self.onBarcodeDetected.connect(self._barcodeDetected)
		self.logger.info('All signals have been binded')

	def _getImage(self):
		# self.logger.info("Getting image...")
		pepperImage = self.vid.getImageRemote(self.videoClient)

		if pepperImage is not None:
			im = Image.fromstring("RGB", (pepperImage[0], pepperImage[1]), str(bytearray(pepperImage[6])))
			im = im.convert('L')

			# self.logger.info("Analyzing image...")
			zImage = zbar.Image(im.size[0], im.size[1], 'Y800', im.tostring())

			if self.scanner.scan(zImage) > 0:
				results = self.scanner.get_results()
				for sym in results:
					sym_type = str(sym.type)
					sym_data = str(sym.data)

				self.logger.info("\tType : %s" % sym_type)
				self.logger.info("\tData : %s" % sym_data)
				self.onBarcodeDetected(sym_type, sym_data)

	def stop(self):
		if self.scanning:
			self.logger.info("Stopping...")
			try:
				self.getImageTask.stop()
				self.logger.info("Stopped.")
				self.scanning = False
			except RuntimeError:
				self.logger.info("Can't stop {}".format(self.serviceName))

	def start(self):
		if not self.scanning:
			self.logger.info("Starting...")
			try:
				getImageCallable = functools.partial(self._getImage)
				self.getImageTask = qi.PeriodicTask()
				self.getImageTask.setCallback(getImageCallable)
				self.getImageTask.setUsPeriod(int(0.5*1000000)) # 0.5 sec
				self.getImageTask.start(True)
				self.logger.info("Started.")
				self.scanning = True
			except RuntimeError:
				self.logger.info("Can't start {}".format(self.serviceName))

	def cleanup(self):
		self.stop()
		self.logger.info("Cleaning...")
		self.vid.unsubscribe(self.videoClient)
		self.logger.info("End!")

# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------

def register_as_service(service_class, session, instance):
	"""
	Registers a service in naoqi
	"""
	service_name = service_class.__name__
	# instance = service_class(session)
	service_id = -1
	try:
		service_id = session.registerService(service_name, instance)
		print 'Successfully registered service: {} (id: {})'.format(service_name, service_id)
		return service_id
	except RuntimeError:
		print '{} already registered, attempt re-register'.format(service_name)
		for info in session.services():
			try:
				if info['name'] == service_name:
					session.unregisterService(info['serviceId'])
					print "Unregistered {} as {}".format(service_name, info['serviceId'])
					break
			except (KeyError, IndexError):
				pass
		service_id = session.registerService(service_name, instance)
		print 'Successfully registered service: {} (id: {})'.format(service_name, service_id)
		return service_id

# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
	"""
	Registers BarcodeReader as a naoqi service.
	"""
	app = qi.Application(sys.argv)
	app.start()

	newService = BarcodeReader(app.session)
	service_id = register_as_service(BarcodeReader, app.session, newService)

	app.run()

	newService.cleanup()

	try:
		app.session.unregisterService(service_id)
		print 'Successfully unregistered service BarcodeReader (id: {})'.format(service_id)
	except RuntimeError:
		print 'Error unregistering service BarcodeReader (id: {})'.format(service_id)



