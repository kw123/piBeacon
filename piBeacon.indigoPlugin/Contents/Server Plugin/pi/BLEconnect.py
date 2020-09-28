#!/usr/bin/env python
# -*- coding: utf-8 -*-
# by Karl Wachs
# mar 2 2016
# version 0.95
##
##	 read sensors and GPIO INPUT and send http to indigo with data
#

##
import	sys, os, subprocess, copy
import	time,datetime
import	json
import	RPi.GPIO as GPIO  
import bluetooth
import bluetooth._bluetooth as bt
import struct
import array
import fcntl


sys.path.append(os.getcwd())
import	piBeaconUtils	as U
import	piBeaconGlobals as G
G.program = "BLEconnect"

				
def readParams():
		global debug, ipOfServer,myPiNumber,passwordOfServer, userIdOfServer, authentication,ipOfServer,portOfServer,sensorList,restartBLEifNoConnect
		global macList 
		global oldRaw, lastRead, BLEconnectMode
		global sensor

		inp,inpRaw,lastRead2 = U.doRead(lastTimeStamp=lastRead)
		if inp == "": return False
		if lastRead2 == lastRead: return False
		lastRead  = lastRead2
		if inpRaw == oldRaw: return False
		oldRaw	   = inpRaw

		oldSensor		  = sensorList

		try:

			U.getGlobalParams(inp)

			sensors = {}
			if "sensors" in inp:	
				if sensor in inp["sensors"]: 
					sensors = inp["sensors"][sensor]

			if sensors == {}:
				U.logger.log(30, u" no {} definitions supplied in sensorList stopping".format(sensor))
				exit()


			if "restartBLEifNoConnect"	in inp:	 restartBLEifNoConnect=		  (inp["restartBLEifNoConnect"])
			if "sensorList"				in inp:	 sensorList=				  (inp["sensorList"])
			if "BLEconnectMode"			in inp:	 BLEconnectMode=			  (inp["BLEconnectMode"])


			macListNew={}

			for devId in sensors :
					thisMAC = sensors[devId]["macAddress"]
					macListNew[thisMAC]={"iPhoneRefreshDownSecs":float(sensors[devId]["iPhoneRefreshDownSecs"]),
										 "iPhoneRefreshUpSecs":float(sensors[devId]["iPhoneRefreshUpSecs"]),
										 "BLEtimeout":max(1.,float(sensors[devId]["BLEtimeout"])),
										 "up":False,
										 "lastTesttt":time.time()-1000.,
										 "lastMsgtt":time.time()-1000. ,
										 "lastData":"xx" ,
										 "quickTest": 0. ,
										 "devId": devId	 }
			for thisMAC in macListNew:
				if thisMAC not in macList:
					macList[thisMAC]=copy.copy(macListNew[thisMAC])
				else:
					macList[thisMAC]["iPhoneRefreshDownSecs"] = macListNew[thisMAC]["iPhoneRefreshDownSecs"]
					macList[thisMAC]["iPhoneRefreshUpSecs"]	  = macListNew[thisMAC]["iPhoneRefreshUpSecs"]
					macList[thisMAC]["BLEtimeout"]	 		  = macListNew[thisMAC]["BLEtimeout"]

			delMac={}
			for thisMAC in macList:
				if thisMAC not in macListNew:
					delMac[thisMAC]=1
			for	 thisMAC in delMac:
				del macList[thisMAC]

			if len(macList)	   == 0:
				U.logger.log(30, u" no BLEconnect definitions supplied in MAClist (2)")
				exit()

			return True
			
		except	Exception, e:
			U.logger.log(50,u"in Line {} has error={}".format(sys.exc_traceback.tb_lineno, e) )
		return False

def tryToConnect(MAC,BLEtimeout,devId):
	global errCount, lastConnect

	if time.time() - lastConnect < 3: time.sleep( max(0,min(0.5,(3.0- (time.time() - lastConnect) ))) )

	retdata	 = {"rssi": -999, "txPower": -999,"flag0ok":0,"byte2":0}
	try:
		for ii in range(5):	 # wait until (wifi) sending is finsihed
			if os.path.isfile(G.homeDir + "temp/sending"):
				#print "delaying hci"
				time.sleep(0.5)
			else:
				 break

		hci_sock = bt.hci_open_dev(devId)
		hci_fd	 = hci_sock.fileno()

		# Connect to device (to whatever you like)
		bt_sock = bluetooth.BluetoothSocket(bluetooth.L2CAP)
		bt_sock.settimeout(BLEtimeout)

		try:
			result	= bt_sock.connect_ex((MAC, 1))	# PSM 1 - Service Discovery
			reqstr = struct.pack("6sB17s", bt.str2ba(MAC), bt.ACL_LINK, "\0" * 17)
			request = array.array("c", reqstr)
			handle = fcntl.ioctl(hci_fd, bt.HCIGETCONNINFO, request, 1)
			handle = struct.unpack("8xH14x", request.tostring())[0]
			cmd_pkt=struct.pack('H', handle)
			# Send command to request RSSI
			socdata = bt.hci_send_req(hci_sock, bt.OGF_STATUS_PARAM, bt.OCF_READ_RSSI, bt.EVT_CMD_COMPLETE, 4, cmd_pkt)
			bt_sock.close()
			hci_sock.close()
			flag0ok	  = struct.unpack('b', socdata[0])[0]
			txPower	  = struct.unpack('b', socdata[1])[0]
			byte2	  = struct.unpack('b', socdata[2])[0]
			rssi	  = struct.unpack('b', socdata[3])[0]
			#print MAC, test0, txPower, test2, signal
			retdata["flag0ok"]	= flag0ok
			retdata["byte2"]	= byte2
			if flag0ok == 0 and not (txPower == rssi and rssi == 0 ):
				retdata["rssi"]	= rssi
				retdata["txPower"]	= txPower
		except IOError:
			# Happens if connection fails (e.g. device is not in range)
			bt_sock.close()
			hci_sock.close()
			for ii in range(30):
				if os.path.isfile(G.homeDir+"temp/stopBLE"):
					time.sleep(5)
				else:
					break
			errCount += 1
			if errCount  < 10: return {}
			subprocess.call("rm {}temp/stopBLE > /dev/null 2>&1".format(G.homeDir), shell=True)
			U.logger.log(20, u"in Line {} has error ... sock.recv error, likely time out ".format(sys.exc_traceback.tb_lineno))
			U.restartMyself(reason="sock.recv error", delay = 10)

	except	Exception, e:
			U.logger.log(30, u"in Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
	U.logger.log(10, "{}:  {}".format(MAC, retdata))
	errCount = 0
	return retdata




#################################
def tryToConnectCommandLine(MAC,BLEtimeout,useHCI):
	global errCount, lastConnect

	if time.time() - lastConnect < 3: time.sleep( max(0,min(0.5,(3.0- (time.time() - lastConnect) ))) )
	retdata	 = {"rssi": -999, "txPower": -999,"flag0ok":0,"byte2":0}
	try:
		for ii in range(5):	 # wait until (wifi) sending is finished
			if os.path.isfile(G.homeDir + "temp/sending"):
				#print "delaying hci"
				time.sleep(0.5)
			else:
				 break
		# Connection timed out
		# Input/output error ok for 1. step, not ok for step 2
		#  stop:  "Device is not available."
	  #timeout -s SIGINT 5s hcitool cc  3C:22:FB:0F:D6:78; hcitool rssi 3C:22:FB:0F:D6:78; hcitool tpl 3C:22:FB:0F:D6:78
	  #sudo timeout -s SIGINT 5s hcitool -i hci0  cc  8C:86:1E:3D:5C:66;sudo hcitool -i hci0 rssi 8C:86:1E:3D:5C:66;sudo hcitool -i hci0 tpl 8C:86:1E:3D:5C:66
		for ii in range(2):
			cmd = "sudo timeout -s SIGINT {:.1f}s hcitool -i {}  cc {};sleep 0.2; hcitool -i {} rssi {} ;sleep 0.2;hcitool -i {} tpl {}".format(BLEtimeout, useHCI, MAC, useHCI,  MAC, useHCI, MAC)
			U.logger.log(10, cmd)
			ret = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
			parts = ret[0].strip("\n").split("\n")
			U.logger.log(10, "{}  1. try ret: {} --- err>>{}<<".format(MAC, ret[0].strip("\n"), ret[1].strip("\n")))

			found = False
			for line in parts:
					if line.find("RSSI return value:") >- 1:
						retdata["rssi"] = int(line.split("RSSI return value:")[1].strip())
						found = True
					if line.find("Current transmit power level:") > -1:
						retdata["txPower"] = int(line.split("Current transmit power level:")[1].strip())
						found = True
			if found: break
			time.sleep(1)

	except  Exception, e:
			U.logger.log(30, u"in Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
			return {}
	
	U.logger.log(10, "{} return data: {}".format(MAC, retdata))
	return retdata



#################################

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
def execBLEconnect():
	global sensorList,restartBLEifNoConnect
	global macList,oldParams
	global oldRaw,	lastRead
	global errCount, lastConnect
	global BLEconnectMode
	global sensor
	BLEconnectMode			= "socket" # or commandLine
	oldRaw					= ""
	lastRead				= 0
	errCount				= 0
	###################### constants #################

	####################  input gios   ...allrpi	  only rpi2 and rpi0--
	oldParams		  = ""
	#####################  init parameters that are read from file 
	sensorList			= "0"
	G.authentication	= "digest"
	restartBLEifNoConnect = True
	sensor				= G.program
	macList				={}
	waitMin				=2.
	oldRaw				= ""
	try:
		onlyThisMAC	  = sys.argv[1]
	except:
		onlyThisMAC = ""


	myPID			= str(os.getpid())
	U.setLogging()
	if onlyThisMAC =="":
		U.killOldPgm(myPID,G.program+".py")# kill  old instances of myself if they are still running
	else:
		U.killOldPgm(myPID, G.program+".py ",param1=onlyThisMAC)  # kill  old instances of myself if they are still running

	loopCount		  = 0
	sensorRefreshSecs = 90
	U.logger.log(30, "starting BLEconnect program ")
	readParams()

	time.sleep(1)  # give HCITOOL time to start

	shortWait			= 1.	# seconds  wait between loop
	lastEverything		= time.time()-10000. # -1000 do the whole thing initially
	lastAlive			= time.time()
	lastData			= {}
	lastRead			= -1

	if U.getIPNumber() > 0:
		U.logger.log(30," no ip number ")
		time.sleep(10)
		exit()


	G.tStart			= time.time() 
	lastMsg				={}
	#print iPhoneRefreshDownSecs
	#print iPhoneRefreshUpSecs
	startSeconds		= time.time()
	lastSignal			= time.time()
	restartCount		= 0
	nextTest			= 60
	nowTest				= 0
	nowP				= False
	oldRetry			= False
	eth0IP, wifi0IP, eth0Enabled, wifiEnabled = U.getIPCONFIG()
	##print eth0IP, wifi0IP, G.eth0Enabled, G.wifiEnabled


	## give other ble functions time to finish
	time.sleep(1)



	#### selct the proper hci bus: if just one take that one, if 2, use bus="uart", if no uart use hci0
	HCIs = U.whichHCI()
	if HCIs["hci"] !={}:
		useHCI,  myBLEmac, BLEid = U.selectHCI(HCIs["hci"], G.BLEconnectUseHCINo,"UART")
		if BLEid < 0:
			U.logger.log(0, "BLEconnect: BLE STACK is not  UP  HCI:{}".format(HCIs))
			sys.exit(1)
	else:
			U.logger.log(0, "BLEconnect: BLE STACK HCI is empty HCI:{}".format(HCIs))
			sys.exit(1)



	U.logger.log(20, "BLEconnect: using mac:{};  useHCI: {}; bus: {}; mode: {} serching for MACs:\n{}".format(myBLEmac, useHCI, HCIs["hci"][useHCI]["bus"], BLEconnectMode , macList))
	lastConnect = time.time()
	while True:

			tt= time.time()
			if tt - nowTest > 15:
				nowP	= False
				nowTest = 0
			if tt - lastRead > 4 :
				newParameterFile = readParams()
				eth0IP, wifi0IP, G.eth0Enabled, G.wifiEnabled = U.getIPCONFIG()
				lastRead=tt

			if restartBLEifNoConnect and (tt - lastSignal > (2*3600+ 600*restartCount)) :
				U.logger.log(30, "requested a restart of BLE stack due to no signal for {:.0f} seconds".format(tt-lastSignal))
				subprocess.call("echo xx > {}temp/BLErestart".format(G.homeDir), shell=True) # signal that we need to restart BLE
				lastSignal = time.time() +30
				restartCount +=1

			nextTest = 300

			for thisMAC in macList:
				if onlyThisMAC !="" and onlyThisMAC != thisMAC: continue
				if macList[thisMAC]["up"]:
					nextTest = min(nextTest, macList[thisMAC]["lastTesttt"] + (macList[thisMAC]["iPhoneRefreshUpSecs"]*0.90)   -tt )
				else:
					nextTest = min(nextTest, macList[thisMAC]["lastTesttt"] + macList[thisMAC]["iPhoneRefreshDownSecs"] -tt - macList[thisMAC]["quickTest"] )

				if True:
					nT= max(int(nextTest),1)
					fTest = max(0.2, nextTest / nT )
					#print "fTest",thisMAC, fTest
					for ii in range(nT):
						tt=time.time()
						if fTest > 0:
							time.sleep(fTest)  
						if not nowP and tt-nowTest > 20.:
							quick = U.checkNowFile(sensor)				  
							if quick:
								for ml in macList :
									if onlyThisMAC != "" and onlyThisMAC != ml: continue
									macList[ml]["lastData"]	   = {"rssi":-999,"txPower":-999}
									macList[ml]["lastTesttt"]  = 0.
									#macList[ml]["lastMsgtt"]  = 0.
									macList[ml]["retryIfUPtemp"] = macList[ml]["retryIfUP"]
									macList[ml]["retryIfUP"] = False
									macList[ml]["up"]		 = False
								nowTest = tt
								nowP	= True
								#print " received BLEconnect now,", thisMAC,onlyThisMAC, "setting nowTest",	 nowTest
								break

						if nowP and tt - nowTest > 5 and tt - nowTest < 10.:
							for ml in macList:
								if onlyThisMAC != "" and onlyThisMAC != ml: continue
								nowTest = 0.
								nowP	= False
								#print "resetting  ", ml, onlyThisMAC, nowTest
			for thisMAC in macList:
				if onlyThisMAC !="" and onlyThisMAC != thisMAC: continue
				tt = time.time()
				#if nowP: print "nowP:	testing: "+thisMAC,macList[ml]["retryIfUP"], tt - macList[thisMAC]["lastTesttt"]
				if macList[thisMAC]["up"]:
					if tt - macList[thisMAC]["lastTesttt"] <= macList[thisMAC]["iPhoneRefreshUpSecs"]*0.90:	  continue
				elif tt - macList[thisMAC]["lastTesttt"] <= macList[thisMAC]["iPhoneRefreshDownSecs"] - macList[thisMAC]["quickTest"]:	 continue


				######### here we actually get the data from the phones ###################
				if BLEconnectMode == "socket":
					data0 = tryToConnect(thisMAC, macList[thisMAC]["BLEtimeout"], BLEid)
				else:
					data0 = tryToConnectCommandLine(thisMAC, macList[thisMAC]["BLEtimeout"], useHCI)
				lastConnect = time.time()


				#print	data0
				macList[thisMAC]["lastTesttt"] =tt

				if	data0 != {}:
					if data0["rssi"] !=-999:
						macList[thisMAC]["up"] =True
						lastSignal	 = time.time()
						restartCount = 0
						if os.path.isfile(G.homeDir + "temp/BLErestart"):
							os.remove(G.homeDir + "temp/BLErestart")

					else:
						macList[thisMAC]["up"] =False

					if data0["rssi"]!=macList[thisMAC]["lastData"] or (tt-macList[thisMAC]["lastMsgtt"]) > (macList[thisMAC]["iPhoneRefreshUpSecs"]-1.): # send htlm message to indigo, if new data, or last msg too long ago
						if macList[thisMAC]["lastData"] != -999 and not macList[thisMAC]["up"] and (tt-macList[thisMAC]["lastMsgtt"]) <	 macList[thisMAC]["iPhoneRefreshUpSecs"]+2.:
							macList[thisMAC]["quickTest"] =macList[thisMAC]["iPhoneRefreshDownSecs"]/2.
							continue
						#print "sending "+thisMAC+" " + datetime.datetime.now().strftime("%M:%S"), macList[thisMAC]["up"] , macList[thisMAC]["quickTest"], data0
						macList[thisMAC]["quickTest"] = 0.
						#print "af -"+datetime.datetime.now().strftime("%M:%S"), macList[thisMAC]["up"], macList[thisMAC]["quickTest"], data0
						macList[thisMAC]["lastMsgtt"]  = tt
						macList[thisMAC]["lastData"] = data0["rssi"]
						data={}
						data["sensors"]					= {"BLEconnect":{macList[thisMAC]["devId"]:{thisMAC:data0}}}
						U.sendURL(data)

				else:
					macList[thisMAC]["up"] = False

			loopCount+=1
			#print "no answer sleep for " + str(iPhoneRefreshDownSecs)
			U.echoLastAlive(G.program)

execBLEconnect()
		
try: 	G.sendThread["run"] = False; time.sleep(1)
except: pass
		
sys.exit(0)		   
