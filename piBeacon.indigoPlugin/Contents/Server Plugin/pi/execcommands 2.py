#!/usr/bin/env python
# -*- coding: utf-8 -*-
# by Karl Wachs
# feb 5 2016
# version 0.7 
##
import SocketServer
import RPi.GPIO as GPIO
import smbus
import re
import json, sys,subprocess, os, time, datetime
import copy

sys.path.append(os.getcwd())
import	piBeaconUtils	as U
import	piBeaconGlobals as G
G.program = "execcommands"

allowedCommands=["up","down","pulseUp","pulseDown","continuousUpDown","analogWrite","disable","myoutput","omxplayer","display","newMessage","resetDevice","startCalibration","getBeaconParameters","file","BLEreport"]

#!/usr/bin/env python
# -*- coding: utf-8 -*-
# by Karl Wachs
# nov 27 2015
# version 0.5 
##

import json
import sys
import subprocess
import time
import datetime
import os


externalGPIO = False

 
def stopPexpect(child, reason):
		U.logger.log(30,reason)
		child.sendline("disconnect")
		time.sleep(0.2)
		child.sendline("disconnect")
		time.sleep(0.2)
		child.sendline("quit\r")
		time.sleep(0.2)
		child.terminate()

def getBeaconParameters(devices):
	global killMyselfAtEnd
	try:
		try: import pexpect
		except:
			os.system("sudo apt-get install pexpect")
			try: import expect
			except: 
				U.logger.log(50,"importing pexpect did not work ")
				return
		
		devices = devices.split(",")
		if len(devices) ==0: return
		os.system("echo getbeaconparameters  > "+G.homeDir+"temp/stopBLE")
		ret = subprocess.Popen("hciconfig hci0 down ",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()  # disenable bluetooth
		time.sleep(0.1)
		ret = subprocess.Popen("hciconfig hci0 up ",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()	 # enable bluetooth

		U.logger.log(20,"get beacon parameters devices:{}".format(devices))
 
		killMyselfAtEnd = True # kill myself after finish

		data ={} 
		for dd in devices:
			if len(dd) < 10: continue
			try:
				gg		= dd.split("=")
				if len(gg) != 2: continue
				mac 	= gg[0]
				params  = gg[1].strip("=")
				state	= []
				uuid	= []
				dType	= []

				for xx in params.split("="):
					yy = xx.split("-")
					if len(yy) !=3: continue
					uuid.append(yy[0])
					state.append(yy[1])
					dType.append(yy[2])
				if len(state) ==0: continue
				child = pexpect.spawn("gatttool -I")
 
				U.logger.log(30,"Connecting to {}".format(mac))
				child.sendline("connect {0}".format(mac))
				ret = child.expect(["Connection successful","Error:",pexpect.TIMEOUT], timeout=5)
				if ret == 0:
					U.logger.log(30,"Connected.., reading parameters")
				elif ret == 1:
					stopPexpect(child," not connected")
					continue
				elif ret == 3:
					stopPexpect(child,"timeout")
					continue
				else:
					stopPexpect(child,"timeout")
					continue

				for ll in range(len(state)):
				# get battery level
					U.logger.log(30,"char-read-uuid {}, dType:{}".format(uuid[ll], dType[ll]) )
					child.sendline("char-read-uuid {}".format(uuid[ll]) )
					child.expect("handle: ", timeout=5)
					child.expect("\r\n", timeout=5)

					batpercent = -2
					ret = child.before.strip()
					ret2 = ret.split("value: ")
					value = ""
					if len(ret2) == 2:  
						try:
							if dType[ll] == "int": value = int(ret2[1].strip(),16)
							if dType[ll] == "str": value = str(ret2[1])
						except:pass
					U.logger.log(30,"{}:  return: {} {} {} ".format(mac, state[ll], ret2, value) )
					if "sensors" not in data: data["sensors"] = {}
					if "getBeaconParameters" not in data["sensors"]: data["sensors"]["getBeaconParameters"] ={}
					if mac not in data["sensors"]["getBeaconParameters"]: data["sensors"]["getBeaconParameters"][mac] ={}
					data["sensors"]["getBeaconParameters"][mac] = {state[ll]:value}
			except Exception, e:
					if unicode(e).find("Timeout") ==-1:
						U.logger.log(50, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
					else:
						U.logger.log(30, u"Line {} has timeout".format(sys.exc_traceback.tb_lineno))
					stopPexpect(child, "exception")
					time.sleep(1)
			else:
				stopPexpect(child, "end of dev")

			
	except Exception, e:
			U.logger.log(50, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
	U.logger.log(30, u"disconnecting")

	U.logger.log(30, u"data:{}".format(data))
	if data !={}:
		U.sendURL(data, wait=False)

	stopPexpect(child, "exit")
	os.system("rm "+G.homeDir+"temp/stopBLE")
	return



def setGPIO(command):
	global PWM, myPID, typeForPWM
	import RPi.GPIO as GPIO
	GPIO.setmode(GPIO.BCM)
	GPIO.setwarnings(False)
	devType = "OUTPUTgpio"



	try:	PWM= command["PWM"] *100
	except: PWM = 100



	if typeForPWM == "PIGPIO" and U.pgmStillRunning("pigpiod"):
		import pigpio
		PIGPIO = pigpio.pi()
		pwmRange  = PWM
		pwmFreq   = PWM
		typeForPWM = "PIGPIO"
	else:
		typeForPWM = "GPIO"
		

	if "cmd" in command:
		cmd= command["cmd"]
		if cmd not in allowedCommands:
			U.logger.log(30, "setGPIO pid=%d, bad command %s  allowed only: %s" %(myPID,unicode(command) ,unicode(allowedCommands))  )
			exit(1)

	if "pin" in command:
		pin= int(command["pin"])
	else:
		U.logger.log(30, "setGPIO pid=%d, pin not included,  bad command %s"%(myPID,unicode(command)) )
		exit(1)



	delayStart = max(0,U.calcStartTime(command,"startAtDateTime")-time.time())
	if delayStart > 0: 
		time.sleep(delayStart)

	if "values" in command:
		values =  command["values"]
	
	
	#	 "values:{analogValue:"analogValue+",pulseUp:"+ pulseUp + ",pulseDown:" + pulseDown + ",nPulses:" + nPulses+"}

	try:
		if "pulseUp" in values:		pulseUp = float(values["pulseUp"])
		else:						pulseUp = 0
		if "pulseDown" in values:	pulseDown = float(values["pulseDown"])
		else:						pulseDown = 0
		if "nPulses" in values:		nPulses = int(values["nPulses"])
		else:						nPulses = 0
		if "analogValue" in values: bits = max(0.,min(100.,float(values["analogValue"])))
		else:						bits = 0
	except	Exception, e:
		U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
		exit(0)

	inverseGPIO = False
	if "inverseGPIO" in command:
		inverseGPIO = command["inverseGPIO"]

	if "devId" in command:
		devId = str(command["devId"])
	else: devId = "0"


	try:
		if cmd == "up":
			GPIO.setup(pin, GPIO.OUT)
			if inverseGPIO: 
				GPIO.output(pin, False)
				if devId !="0": U.sendURL({"outputs":{"OUTPUTgpio-1-ONoff":{devId:{"actualGpioValue":"low"}}}})
			else:
				GPIO.output(pin, True)
				if devId !="0": U.sendURL({"outputs":{"OUTPUTgpio-1-ONoff":{devId:{"actualGpioValue":"high"}}}})
		

		elif cmd == "down":
			GPIO.setup(pin, GPIO.OUT)
			if inverseGPIO: 
				GPIO.output(pin, True)
				if devId !="0": U.sendURL({"outputs":{"OUTPUTgpio-1-ONoff":{devId:{"actualGpioValue":"high"}}}})
			else: 
				GPIO.output(pin, False )
				if devId !="0": U.sendURL({"outputs":{"OUTPUTgpio-1-ONoff":{devId:{"actualGpioValue":"low"}}}})

		elif cmd == "analogWrite":
			if inverseGPIO:
				value = (100-bits)	# duty cycle on xx hz
			else:
				value =   bits	 # duty cycle on xxx hz 
			value = int(value)
			U.logger.log(10, "analogwrite pin = {};    duty cyle: {};  PWM={}; using {}".format(pin, value, PWM, typeForPWM) )
			if value > 0:
				U.sendURL({"outputs":{"OUTPUTgpio-1":{devId:{"actualGpioValue":"high"}}}})
			else:
				U.sendURL({"outputs":{"OUTPUTgpio-1":{devId:{"actualGpioValue":"low"}}}})

			if typeForPWM == "PIGPIO": 	
				#U.logger.log(20, "..  setting PIGPIO {}  {}  {}".format(pwmFreq, pwmRange,  value) )
				PIGPIO.set_mode(pin, pigpio.OUTPUT)
				PIGPIO.set_PWM_frequency(pin, pwmFreq)
				PIGPIO.set_PWM_range(pin, pwmRange)
				PIGPIO.set_PWM_dutycycle(pin, value)

			else:
				GPIO.setup(pin, GPIO.OUT)
				p = GPIO.PWM(pin, PWM)	# 
				p.start(int(value))	 # start the PWM with  the proper duty cycle
			time.sleep(1000000000)	# we need to keep it alive otherwise it will stop  this is > 1000 days ~ 3 years


		elif cmd == "pulseUp":
			GPIO.setup(pin, GPIO.OUT)
			if inverseGPIO: GPIO.output(pin, False)
			else:			GPIO.output(pin, True)
			time.sleep(pulseUp)
			if inverseGPIO: GPIO.output(pin, True)
			else:			GPIO.output(pin, False)


		elif cmd == "pulseDown":
			GPIO.setup(pin, GPIO.OUT)
			if inverseGPIO: GPIO.output(pin, True)
			else:			GPIO.output(pin, False)
			time.sleep(pulseDown)
			if inverseGPIO: GPIO.output(pin, False)
			else:			GPIO.output(pin, True)

		elif cmd == "continuousUpDown":
			GPIO.setup(pin, GPIO.OUT)
			for ii in range(nPulses):
				if inverseGPIO:	  GPIO.output(pin, False)
				else:			  GPIO.output(pin, True)
				time.sleep(pulseUp)
				if inverseGPIO:	  GPIO.output(pin, True)
				else:			  GPIO.output(pin, False)
				time.sleep(pulseDown)

		U.removeOutPutFromFutureCommands(pin, devType)
			


	except	Exception, e:
		U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))

	return 


def execCMDS(data):
	global execcommands, PWM

	for ijji in range(1):
			try:
				next = json.loads(data)
			except	Exception, e:
					U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
					U.logger.log(30," bad command: json failed  %s"%unicode(data))

			#print next
			#print "next command: "+unicode(next)
			U.logger.log(10,"next command: "+unicode(data))
			cmd= next["command"]

			for cc in next:
				if cc == "startAtDateTime":
					next["startAtDateTime"] = time.time() + next["startAtDateTime"]
				


			if "restoreAfterBoot" in next:
				restoreAfterBoot= next["restoreAfterBoot"]
			else:
				restoreAfterBoot="0"


			if cmd =="general":
				if "cmdLine" in next:
					os.system(next["cmdLine"] )	 
					continue


			if cmd =="file":
				if "fileName" in next and "fileContents" in next:
					#print next
					try:
						m = "w"
						if "fileMode" in next and next["fileMode"].lower() =="a": m="a"
						#print "write to",next["fileName"], json.dumps(next["fileContents"]), m
						f=open(next["fileName"],m)
						f.write("{}".format(json.dumps(next["fileContents"]) )) 
						f.close()
						if "touchFile" in next and next["touchFile"]:
							os.system("echo	 "+str(time.time())+" > "+G.homeDir+"temp/touchFile" )
						os.system("sudo chown -R  pi  "+G.homeDir)
					except	Exception, e:
						U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				continue


			if cmd =="getBeaconParameters":
				try:
					if "device" not in next: continue
					getBeaconParameters(next["device"])
				except	Exception, e:
						U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				continue

			if cmd =="BLEreport":
				try:
					U.killOldPgm(-1,"master.py")
					U.killOldPgm(-1,"beaconloop.py")
					U.killOldPgm(-1,"BLEconnect.py")
					U.getIPNumber()
					data   = {"BLEreport":{},"pi":str(G.myPiNumber)}
					
					cmd = "sudo hciconfig "
					dataW = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
					U.logger.log(10, unicode(dataW))
					data   = {"BLEreport":{}}
					data["BLEreport"]["hciconfig"]			  = dataW
					cmd = "sudo hciconfig hci0 down; sudo hciconfig hci0 up ; sudo timeout -s SIGINT 15s hcitool lescan "
					dataW = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
					U.logger.log(10, unicode(dataW))
					data["BLEreport"]["hcitool lescan"]		  = dataW
					cmd = "sudo timeout -s SIGINT 25s hcitool scan "
					dataW = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
					U.logger.log(10, unicode(dataW)) 
					data["BLEreport"]["hcitool scan"]		  = dataW
					U.logger.log(10, unicode(data))
					U.sendURL(data,squeeze=False)
					time.sleep(2)
					os.system("sudo reboot")
					exit()
				except	Exception, e:
						U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				continue



			if "device" not in next:
				U.logger.log(30," bad cmd no device given "+unicode(next))
				continue
				
			device=next["device"]
			
			if device.lower()=="setsteppermotor":
				cmdOut = json.dumps(next)
				if cmdOut != "":
					try:
						f=open(G.homeDir+"temp/setStepperMotor.inp","a")
						f.write(cmdOut+"\n")
						f.close()
					except	Exception, e:
						U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				continue
			
			if device.lower()=="output-display":
				cmdOut = json.dumps(next)
				if cmdOut != "":
					try:
						#print "execcmd", cmdOut
						if not U.pgmStillRunning("display.py"):
							os.system("/usr/bin/python "+G.homeDir+"display.py &" )
						f=open(G.homeDir+"temp/display.inp","a")
						f.write(cmdOut+"\n")
						f.close()
						f=open(G.homeDir+"display.inp","w")
						f.write(cmdOut+"\n")
						f.close()
					except	Exception, e:
						U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				continue


			if device.lower()=="output-neopixel":
				cmdOut = json.dumps(next)
				if cmdOut != "":
					try:
						#print "execcmd", cmdOut
						if	not U.pgmStillRunning("neopixel.py"):
							os.system("/usr/bin/python "+G.homeDir+"neopixel.py	 &" )
						else:
							f=open(G.homeDir+"temp/neopixel.inp","a")
							f.write(cmdOut+"\n")
							f.close()
							f=open(G.homeDir+"neopixel.inp","w")
							f.write(cmdOut+"\n")
							f.close()
					except	Exception, e:
						U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				continue




			if cmd not in allowedCommands:
				U.logger.log(30," bad cmd not in allowed commands {} \n{}".format(cmd, allowedCommands))
				continue


			if "values" in next:
				values = next["values"]
			else:
				values =""

			startAtDateTime =unicode(time.time())
			if "startAtDateTime" in next:
				startAtDateTime = next["startAtDateTime"]

			if "inverseGPIO" in next:
				inverseGPIO = next["inverseGPIO"]
			else:
				inverseGPIO = False


			if "devId" in next:
				devId = next["devId"]
			else:
				devId = 0




			if	cmd == "newMessage":
					if next["device"].find(",")> 1:
						list = next["device"].split(",")
					elif next["device"]== "all":
						list = G.programFiles + G.specialSensorList + G.specialOutputList + G.programFiles
					else:
						list = [next["device"]]
					for pgm in list:
						os.system("echo x > "+G.homeDir+"temp/"+pgm+".now")
					continue


			if	cmd == "resetDevice":
					if next["device"].find(",")> 1:
						list = next["device"].split(",")
					elif next["device"]== "all":
						list = G.programFiles + G.specialSensorList + G.specialOutputList + G.programFiles
					else:
						list = [next["device"]]
					for pgm in list:
						os.system("echo x > "+G.homeDir+"temp/"+pgm+".reset")
					continue




			if	cmd == "startCalibration":
					if next["device"].find(",")> 1:
						list = next["device"].split(",")
					elif next["device"]== "all":
						list = G.specialSensorList
					else:
						list = [next["device"]]
					for pgm in list:
						os.system("echo x > "+G.homeDir+"temp/"+pgm+".startCalibration")
					continue




			if device=="setMCP4725":
						try:
							i2cAddress=str(next["i2cAddress"])
							if cmd =="disable" :
								if str(int(i2cAddress)+1000) in execcommands:
									del execcommands[str(int(i2cAddress)+1000)]
							cmdJ= json.dumps({"cmd":cmd,"i2cAddress":i2cAddress,"startAtDateTime":startAtDateTime,"values":values, "devId":devId })
							U.logger.log(10,json.dumps(next))
							cmdOut="python "+G.homeDir+"setmcp4725.py '"+ cmdJ+"'  &"
							U.logger.log(10," cmd= %s"%cmdOut)
							os.system(cmdOut)
							if restoreAfterBoot == "1":
								execcommands[str(int(i2cAddress)+1000)] = next
							else:
								try: del execcommands[str(int(i2cAddress)+1000)]
								except:pass

						except	Exception, e:
							U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
						continue

			if device=="setPCF8591dac":
						try:
							i2cAddress=str(next["i2cAddress"])
							if cmd =="disable" :
								del execcommands[str(int(i2cAddress)+1000)]
								continue
							cmdJ= json.dumps({"cmd":cmd,"i2cAddress":i2cAddress,"startAtDateTime":startAtDateTime,"values":values, "devId":devId})
							U.logger.log(10,json.dumps(next))
							cmdOut="python "+G.homeDir+"setPCF8591dac.py '"+ cmdJ+"'  &"
							U.logger.log(10," cmd= %s"%cmdOut)
							os.system(cmdOut)
							if restoreAfterBoot == "1":
								execcommands[str(int(i2cAddress)+1000)] = next
							else:
								try: del execcommands[str(int(i2cAddress)+1000)]
								except:pass

						except	Exception, e:
							U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
						continue


			if device=="OUTgpio" or device.find("OUTPUTgpio")> -1:
						try:
							pinI = int(next["pin"])
							pin = str(pinI)
						except	Exception, e:
							U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
							U.logger.log(30,"bad pin "+unicode(next))
							continue
						#print "pin ok"
						if "values" in next: values= next["values"]
						else:				 values={}
   
						if restoreAfterBoot == "1":
							execcommands[str(pin)] = next
						else:
							try: del execcommands[str(pin)]
							except: pass
						if not externalGPIO:
							#kill last execcommand for THIS pin, ps -ef grep string: eg '"pin": "12"'  with '' !!!
							psefString = (json.dumps({"pin":str(pin)})).strip("{}")
							U.killOldPgm(myPID,"execcommands.py ", param1="'"+psefString+"'")
						if cmd =="disable":
							continue
						cmdJ= {"pin":pin,"cmd":cmd,"startAtDateTime":startAtDateTime,"values":values, "inverseGPIO": inverseGPIO,"debug":G.debug,"PWM":PWM, "devId":devId}
						cmdJD = json.dumps(cmdJ)
						if externalGPIO:
							cmdOut="python "+G.homeDir+"setGPIO.py '"+ cmdJD+"' &"
							U.logger.log(10,"cmd= %s"%cmdOut)
							os.system(cmdOut)
						else:
							U.logger.log(10, "setGPIO curr_pid=%d,  command :%s" %(myPID,cmdJD) )
							setGPIO(cmdJ)
						continue

			if device=="myoutput":
						try:
							text   = next["text"]
							cmdOut= "/usr/bin/python "+G.homeDir+"myoutput.py "+text+"	&"
							U.logger.log(10,"cmd= %s"%cmdOut)
							os.system(cmdOut)
						except	Exception, e:
							U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
						continue

			if device=="playSound":
						cmdOut=""
						try:
							if	 cmd  == "omxplayer":
								cmdOut = json.dumps({"player":"omxplayer","file":G.homeDir+"soundfiles/"+next["soundFile"]})
							elif cmd  == "aplay":
								cmdOut = json.dumps({"player":"aplay","file":G.homeDir+"soundfiles/"+next["soundFile"]})
							else:
								U.logger.log(30, u"bad command : player not right =" + cmd)
							if cmdOut != "":
								U.logger.log(10,"cmd= %s"%cmdOut)
								os.system("/usr/bin/python playsound.py '"+cmdOut+"' &" )
						except	Exception, e:
							U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
						continue

			U.logger.log(30,"bad device number/number: "+device)
	f=open(G.homeDir+"execcommands.current","w")
	f.write(json.dumps(execcommands))
	f.close()

	return


def readParams():
	global execcommands, PWM, typeForPWM, killMyselfAtEnd
	killMyselfAtEnd = False
	typeForPWM = "GPIO"
	inp,inpRaw = U.doRead()
	if inp == "": return
	U.getGlobalParams(inp)
	try:
		if u"GPIOpwm"				in inp:	 PWM=			int(inp["GPIOpwm"])
		if u"typeForPWM"			in inp:	 typeForPWM=	inp["typeForPWM"]
	except	Exception, e:
		U.logger.log(30, u"Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
		 

if True: #__name__ == "__main__":
	global execcommands, PWM, myPID
	PWM = 100
	myPID		= int(os.getpid())
	U.setLogging()
	readParams()

#### read exec command list for restart values, update if needed and write back
	execcommands={}
	#print "execcommands" , sys.argv
	if os.path.isfile(G.homeDir+"execcommands.current"):
		try:
			f = open(G.homeDir+"execcommands.current","r")
			xx = f.read()
			f.close()
			execcommands=json.loads(xx)
		except:
			try:	f.close()
			except: pass
			execcommands={}
	else:
		execcommands={}

	U.logger.log(30, u"exec cmd: {}".format(sys.argv))
		
	execCMDS(sys.argv[1])
	time.sleep(0.5)
	U.logger.log(20, u"exec cmd: killing myself at PID{}".format(myPID))
	if killMyselfAtEnd: os.system(" sudo kill -9 "+str(myPID) )