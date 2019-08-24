#!/usr/bin/env python
# -*- coding: utf-8 -*-
# by Karl Wachs
# mar 2 2016
# version 0.95
##
##	 read GPIO INPUT and send http to indigo with data if pulses detected
#

##

import	sys, os, subprocess, copy
import	time,datetime
import	json
import	RPi.GPIO as GPIO  

sys.path.append(os.getcwd())
import	piBeaconUtils	as U
import	piBeaconGlobals as G
G.program = "INPUTpulse"
GPIO.setmode(GPIO.BCM)


def checkReset():
	global	INPUTcount
	INPUTcount2 = U.checkresetCount(INPUTcount)
	if INPUTcount2 != INPUTcount:
		INPUTcount = copy.copy(INPUTcount2)
		return True
	return False

def readParams():
	global sensor, sensors
	global INPgpioType,INPUTcount,INPUTlastvalue
	global GPIOdict, restart
	global oldRaw, lastRead
	try:
		restart = False


		inp,inpRaw,lastRead2 = U.doRead(lastTimeStamp=lastRead)
		if inp == "": return
		if lastRead2 == lastRead: return
		lastRead  = lastRead2
		if inpRaw == oldRaw: return
		oldRaw	   = inpRaw

		oldSensors		  = sensors

		U.getGlobalParams(inp)
		if "sensors"			in inp : sensors =				(inp["sensors"])
		if "debugRPI"			in inp:	 G.debug=			  int(inp["debugRPI"]["debugRPISENSOR"])

		if sensor not in sensors:
			U.logger.log(10,	"no "+ G.program+" sensor defined, exiting")
			exit()

		sens= sensors[sensor]
		#print "sens:", sens
		found ={str(ii):{"RISING":0,"FALLING":0,"BOTH":0 } for ii in range(100)}
		for devId in sens:
			sss= sens[devId]
			if "gpio"							not in sss: continue
			if "deadTime"						not in sss: continue
			if "risingOrFalling"				not in sss: continue
			if "minSendDelta"					not in sss: continue
			if "bounceTime"						not in sss: continue
			if "deadTimeBurst"					not in sss: continue
			if "inpType"						not in sss: continue
			if "timeWindowForBursts"			not in sss: continue
			if "timeWindowForContinuousEvents"	not in sss: continue
			if "minBurstsinTimeWindowToTrigger" not in sss: continue

			gpio						= sss["gpio"]
			risingOrFalling				= sss["risingOrFalling"]
			inpType						= sss["inpType"]

			try:	bounceTime			= int(sss["bounceTime"])
			except: bounceTime			= 10

			try:	minSendDelta		= int(sss["minSendDelta"])
			except: minSendDelta		= 1

			try:	deadTime			= float(sss["deadTime"])
			except: deadTime			= 1

			try:	deadTimeBurst		= float(sss["deadTimeBurst"])
			except: deadTimeBurst		= 1

			try:	timeWindowForBursts = int(sss["timeWindowForBursts"])
			except: timeWindowForBursts = -1

			try:	minBurstsinTimeWindowToTrigger = int(sss["minBurstsinTimeWindowToTrigger"])
			except: minBurstsinTimeWindowToTrigger = -1

			try:	timeWindowForContinuousEvents = float(sss["timeWindowForContinuousEvents"])
			except: timeWindowForContinuousEvents = -1
			try:	minSendDelta = float(sss["minSendDelta"])
			except: minSendDelta = -1



			found[gpio][risingOrFalling]		 = 1
			if gpio in GPIOdict and "risingOrFalling" in GPIOdict[gpio]: 
					if GPIOdict[gpio]["bounceTime"] !=	bounceTime: 
						restart=True
						return
					if GPIOdict[gpio]["risingOrFalling"] !=	 risingOrFalling: 
						restart=True
						return
					GPIOdict[gpio]["deadTime"]								= deadTime
					GPIOdict[gpio]["deadTimeBurst"]							= deadTimeBurst
					GPIOdict[gpio]["devId"]									= devId
					GPIOdict[gpio]["minSendDelta"]							= minSendDelta
					GPIOdict[gpio]["minBurstsinTimeWindowToTrigger"]		= minBurstsinTimeWindowToTrigger
					GPIOdict[gpio]["timeWindowForBursts"]					= timeWindowForBursts
					GPIOdict[gpio]["timeWindowForContinuousEvents"]			= timeWindowForContinuousEvents
					GPIOdict[gpio]["lastsendBurst"]							= 0
					GPIOdict[gpio]["lastsendCount"]							= 0
					GPIOdict[gpio]["lastsendContinuousEvent"]				= 0
					if inpType != GPIOdict[gpio]["inpType"]:
						if	 inpType == "open":
							GPIO.setup(int(gpio), GPIO.IN)
						elif inpType == "high":
							GPIO.setup(int(gpio), GPIO.IN, pull_up_down=GPIO.PUD_UP)
						elif inpType == "low":
							GPIO.setup(int(gpio), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
					GPIOdict[gpio]["inpType"]	 = inpType
					continue 
			elif gpio in GPIOdict and "risingOrFalling" not in GPIOdict[gpio]: 
				print "setting up ",risingOrFalling
				GPIOdict[gpio]={
								  "devId":							devId,
								  "inpType":						inpType,
								  "minSendDelta":					minSendDelta,
								  "bounceTime":						bounceTime,
								  "deadTime":						deadTime,
								  "deadTimeBurst":					deadTimeBurst,
								  "risingOrFalling":				risingOrFalling,
								  "timeWindowForBursts":			timeWindowForBursts,
								  "timeWindowForContinuousEvents":	timeWindowForContinuousEvents,
								  "minBurstsinTimeWindowToTrigger": minBurstsinTimeWindowToTrigger,
								  "lastSignal":						0,
								  "lastsendCount":					0,
								  "lastsendBurst":					0,
								  "lastsendContinuousEvent":		0,
								  "count":							0 }
				print  GPIOdict				  
				if	 inpType == "open":
					GPIO.setup(int(gpio), GPIO.IN)
				elif inpType == "high":
					GPIO.setup(int(gpio), GPIO.IN, pull_up_down=GPIO.PUD_UP)
				elif inpType == "low":
					GPIO.setup(int(gpio), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
				if	risingOrFalling == "RISING": 
					if bounceTime > 0:
						GPIO.add_event_detect(int(gpio), GPIO.RISING,	callback=RISING,  bouncetime=bounceTime)  
					else:
						GPIO.add_event_detect(int(gpio), GPIO.RISING,	callback=RISING)  
				elif  risingOrFalling == "FALLING": 
					if bounceTime > 0:
						GPIO.add_event_detect(int(gpio), GPIO.FALLING,	callback=FALLING, bouncetime=bounceTime)  
					else:
						GPIO.add_event_detect(int(gpio), GPIO.FALLING,	callback=FALLING)  
				else:
					if bounceTime > 0:
						GPIO.add_event_detect(int(gpio), GPIO.BOTH,		callback=BOTH, bouncetime=bounceTime)  
					else:
						GPIO.add_event_detect(int(gpio), GPIO.BOTH,		callback=BOTH)  
				GPIOdict[gpio]["inpType"]	 = inpType

			elif gpio not in GPIOdict: # change: reboot 
				GPIOdict[gpio]={
								  "devId":							devId,
								  "inpType":						inpType,
								  "minSendDelta":					minSendDelta,
								  "bounceTime":						bounceTime,
								  "deadTime":						deadTime,
								  "deadTimeBurst":					deadTimeBurst,
								  "risingOrFalling":				risingOrFalling,
								  "timeWindowForBursts":			timeWindowForBursts,
								  "timeWindowForContinuousEvents":	timeWindowForContinuousEvents,
								  "minBurstsinTimeWindowToTrigger": minBurstsinTimeWindowToTrigger,
								  "lastSignal":						0,
								  "lastsendCount":					0,
								  "lastsendBurst":					0,
								  "lastsendContinuousEvent":		0,
								  "count":							0 }
				print  ""				
				if	 inpType == "open":
					GPIO.setup(int(gpio), GPIO.IN)
				elif inpType == "high":
					GPIO.setup(int(gpio), GPIO.IN, pull_up_down=GPIO.PUD_UP)
				elif inpType == "low":
					GPIO.setup(int(gpio), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
				if	risingOrFalling == "RISING": 
					if bounceTime > 0:
						GPIO.add_event_detect(int(gpio), GPIO.RISING,	callback=RISING,  bouncetime=bounceTime)  
					else:
						GPIO.add_event_detect(int(gpio), GPIO.RISING,	callback=RISING)  
				elif  risingOrFalling == "FALLING": 
					if bounceTime > 0:
						GPIO.add_event_detect(int(gpio), GPIO.FALLING,	callback=FALLING, bouncetime=bounceTime)  
					else:
						GPIO.add_event_detect(int(gpio), GPIO.FALLING,	callback=FALLING)  
				else:
					if bounceTime > 0:
						GPIO.add_event_detect(int(gpio), GPIO.BOTH,		callback=BOTH, bouncetime=bounceTime)  
					else:
						GPIO.add_event_detect(int(gpio), GPIO.BOTH,		callback=BOTH)  
				GPIOdict[gpio]["inpType"]	 = inpType
				
		oneFound = False
		restart=False
		delGPIO={}
		for gpio in GPIOdict:
			for risingOrFalling in["FALLING","RISING","BOTH"]:
				if found[gpio][risingOrFalling]==1: 
					oneFound = True
					continue
				if risingOrFalling in GPIOdict:
					restart=True
					continue
			if GPIOdict[gpio] == {}: delGPIO[gpio]=1
		for gpio in delGPIO:
			if gpio in GPIOdict: del GPIOdict[gpio]
		
		if not oneFound:
			U.logger.log(10,	"no	 gpios setup, exiting")
			exit()
		if	restart:
			U.logger.log(10,	"gpios edge channel deleted, need to restart")
			U.restartMyself(param="", reason=" new definitions")
			
		U.logger.log(10,	"GPIOdict: " +unicode(GPIOdict))
	except	Exception, e:
		U.logger.log(30, u"in Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
				

def setupSensors():

		U.logger.log(10, "starting setup GPIOs ")

		ret=subprocess.Popen("modprobe w1-gpio" ,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
		if len(ret[1]) > 0:
			U.logger.log(30, "starting GPIO: return error "+ ret[0]+"\n"+ret[1])
			return False

		ret=subprocess.Popen("modprobe w1_therm",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
		if len(ret[1]) > 0:
			U.logger.log(30, "starting GPIO: return error "+ ret[0]+"\n"+ret[1])
			return False

		return True
 
 
def FALLING(gpio):	
	fillGPIOdict(gpio,"FALLING")
	 
def RISING(gpio):
	fillGPIOdict(gpio,"RISING")
	
def BOTH(gpio):
	fillGPIOdict(gpio,"BOTH")

def fillGPIOdict(gpio,risingOrFalling):
	global INPUTcount, GPIOdict, sensor, BURSTS, lastGPIO, contEVENT, sensors
	
	ggg = GPIOdict[str(gpio)]
	tt= time.time()
	countChanged = False
	#U.logger.log(30,"{} edge on gpio: {}".format(risingOrFalling, gpio))
	if tt- ggg["lastSignal"] > ggg["deadTime"]:	 
		ggg["count"]+=1
		INPUTcount[int(gpio)]+=1
		ggg["lastSignal"] = tt
		U.logger.log(10,"{} edge on gpio: {},	count: {}  timest: {:6.1f}, lastSendC: {:6.1f}, minSendDelta:{}".format(risingOrFalling, gpio, ggg["count"], tt, ggg["lastsendCount"], ggg["minSendDelta"]))
		countChanged = True

	###############	 this EVENTtype requires a minBurstsinTimeWindowToTrigger  in timeWindowForBursts to trigger ###
	burst=0
	bbb =  BURSTS[gpio]
	if ggg["minBurstsinTimeWindowToTrigger"] > 0:
		ll	=len(bbb)
		for kk in range(ll):
			ii = ll - kk -1
			if tt-bbb[ii][0] > ggg["timeWindowForBursts"]: 
				del bbb[ii]
		U.logger.log(20, "BURST: "+str(ll)+""+str(tt)+"	 "+ str(bbb)+" "+str(ggg["timeWindowForBursts"] ))
		ll	=len(bbb)
		if ll == 0	or (tt - bbb[-1][0]  > ggg["deadTimeBurst"]): 
			bbb.append([tt,1])
			U.logger.log(10, "BURST: in window "+str(ggg["timeWindowForBursts"]))
			ll	+=1
			delupto = -1
			for kk in range(ll):
					ii = ll - kk -1
					bbb[ii][1]+=1
					if bbb[ii][1] >= ggg["minBurstsinTimeWindowToTrigger"]:
						U.logger.log(10, "BURST triggered "+ risingOrFalling+" edge .. on %d2"%gpio+" gpio,  burst# "+unicode(ii)+";	#signals="+ unicode(bbb[ii][1])+ "--  in "+ unicode(ggg["timeWindowForBursts"]) +"secs time window")
						burst	= tt
						delupto = ii-1
						bbb[ii][1]	= tt+ggg["timeWindowForBursts"]
						break
			if delupto >0:
				for kk in range(delupto):
					del bbb[delupto - kk -1]



	###############	 this EVENTtype requires a pulse to start the CONT event, will extend event if new pulse arrives before timeWindowForContinuousEvents is over  ###
	cEVENTtt=0
	if ggg["timeWindowForContinuousEvents"] > 0:
		if contEVENT[gpio] == -1 or contEVENT[gpio] == 0:  # new event 
			cEVENTtt = tt
		elif  contEVENT[gpio] > 0 and tt - contEVENT[gpio]	> ggg["timeWindowForContinuousEvents"]:
			# was expired send off then send ON 
			data = {"sensors":{sensor:{ggg["devId"]:{}}}}
			data["sensors"][sensor][ggg["devId"]]["continuous"]		 = -1
			ggg["lastsendContinuousEvent"] = tt-20000
			cEVENTtt = tt
		#  or just conti nue old c event = just update contEVENT not need to send data 
		contEVENT[gpio] =  tt
		U.logger.log(10, "cEVENT(1): "+str(tt)+"; cEVENTtt="+ unicode(cEVENTtt)  )

	
	data = {"sensors":{sensor:{ggg["devId"]:{}}}}

	if (tt - ggg["lastsendBurst"] > ggg["minSendDelta"]) and  burst > 0 :  
			data["sensors"][sensor][ggg["devId"]]["burst"]		= int(burst)
			data["sensors"][sensor][ggg["devId"]]["count"]		= ggg["count"]
			ggg["lastsendBurst"] = tt
			ggg["lastsendCount"] = tt
			if burst >0:
				lastGPIO= U.doActions(data["sensors"],lastGPIO, sensors, sensor,theAction="PulseBurst")

	if (tt - ggg["lastsendContinuousEvent"] > ggg["minSendDelta"]) and	cEVENTtt > 0 :	
			data["sensors"][sensor][ggg["devId"]]["continuous"]		 = int(cEVENTtt)
			data["sensors"][sensor][ggg["devId"]]["count"]			 = ggg["count"]
			ggg["lastsendContinuousEvent"] = tt
			ggg["lastsendCount"] = tt
			if cEVENTtt >0:
				lastGPIO= U.doActions(data["sensors"],lastGPIO, sensors, sensor,theAction="PulseContinuous")

	if (tt - ggg["lastsendCount"] > ggg["minSendDelta"]) and countChanged:	
			data ["sensors"][sensor][ggg["devId"]]["count"]		= ggg["count"]
			ggg["lastsendCount"] = tt

	if data["sensors"][sensor][ggg["devId"]] !={}:
			U.sendURL(data,wait=False)
			U.writeINPUTcount(INPUTcount)

def resetContinuousEvents():
	global GPIOdict, contEVENT, sensor
	tt = time.time()
	for gpio in GPIOdict:
		ggg = GPIOdict[gpio]
		if ggg["timeWindowForContinuousEvents"] > 0:
			igpio= int(gpio)
			if	contEVENT[igpio] > 0:
				if	tt - contEVENT[igpio]  > ggg["timeWindowForContinuousEvents"]:
					contEVENT[igpio] =	-1
					# was expired send off then send ON 
					data = {"sensors":{sensor:{ggg["devId"]:{}}}}
					data["sensors"][sensor][ggg["devId"]]["continuous"] = -1
					U.sendURL(data,wait=False)

  
def execMain():
	global sensors, sensor, INPUTcount
	global oldParams
	global GPIOdict, restart, BURSTS, lastGPIO, contEVENT
	global oldRaw,	lastRead, lastSend
	global minSendDelta
	oldRaw					= ""
	lastRead				= 0
	minSendDelta			= 10
	###################### constants #################
	sensor			  = G.program

	INPUTlastvalue	  = ["-1" for i in range(100)]
	INPUTcount		  = [0	  for i in range(100)]
	BURSTS			  = [[]	  for i in range(50)]
	contEVENT		  = [0	  for i in range(50)]
	lastGPIO		  = [""	  for ii in range(50)]
	#i2c pins:		  = gpio14 &15
	# 1 wire		  = gpio4
	oldParams		  = ""
	GPIOdict		  = {}
	restart			  = False
	countReset		  = False


	U.setLogging()


	if not setupSensors():
		print " gpio are not setup"
		exit()


	myPID		= str(os.getpid())
	U.killOldPgm(myPID,G.program+".py")# old old instances of myself if they are still running


	sensors			  ={}
	loopCount		  = 0

	U.logger.log(30, "starting "+G.program+" program")

	readParams()
	INPUTcount = U.readINPUTcount()



	# check if everything is installed
	for i in range(100):
		if not setupSensors(): 
			time.sleep(10)
			if i%50==0: U.logger.log(30,"sensor libs not installed, need to wait until done")
		else:
			break	 
		

	G.lastAliveSend		= time.time()
	# set alive file at startup


	if U.getIPNumber() > 0:
		U.logger.log(30," sensors no ip number  exiting ")
		time.sleep(10)
		exit()

	quick  = 0

	G.tStart = time.time() 
	lastRead = time.time()
	shortWait =0.1
	lastSend  = 0
	lastEcho  = 0
	while True:
		try:
			tt= time.time()
		
			resetContinuousEvents()

			if loopCount %10 ==0:
				data0={}
				quick = U.checkNowFile(G.program)
				U.manageActions("-loop-")
				if loopCount%5==0:
					countReset = checkReset()
					if countReset:
						for gpio in GPIOdict:
							if INPUTcount[int(gpio)] ==0: 
								GPIOdict[gpio]["count"]=0
				
		
					##U.checkIfAliveNeedsToBeSend(lastMsg)
					if time.time()- lastRead > 10:
							readParams()
							lastRead = time.time()

					if restart:
						U.restartMyself(param="", reason=" new definitions")

				if time.time() - lastEcho  > 300:
						lastEcho = time.time()
						U.echoLastAlive(G.program)
			
				if ((time.time() - lastSend >  minSendDelta) and loopCount > 10 ) or countReset:
					data={"sensors":{sensor:{}}}
					for gpio in GPIOdict:
							if "devId" not in GPIOdict[gpio]: continue	
							devId = GPIOdict[gpio]["devId"]
							data["sensors"][sensor][devId] = {"count": GPIOdict[gpio]["count"]}
					U.sendURL(data,wait=False)
					lastSend = time.time()
					loopCount = 0
					countReset = False


			loopCount+=1
			time.sleep(shortWait)
		except	Exception, e:
			U.logger.log(30, u"in Line {} has error={}".format(sys.exc_traceback.tb_lineno, e))
			time.sleep(5.)

execMain()
sys.exit(0)
