#!/usr/bin/python

from ghmm import *
from itertools import izip_longest
import dictionaryMethods as dictMeth
import handleJsonFile as jsonf
import handleOS as system

def train(fixedLength, pathToGoodware, pathToDictionary):
	"""
	Train the Hidden Markov Model with traces of goodware, using the tool 'GHMM'
	:param fixedLength: length to which the samples are fixed
	:param pathToGoodware: path to folder containing the benign traces for training the model
	:param pathToDictionary: path to the dictionary file that contains the method names of all API calls 
	:type fixedLength: int
	:type pathToGoodware: string
	:type pathToDictionary: string
	:return: the trained model and the domain of observations
	:rtype: ghmm.DiscreteEmissionHMM, ghmm.Alphabet
	"""
	dictionary = dictMeth.getMethodDictionary(pathToDictionary)
	sigma, A, B, pi = initParams(len(dictionary))
	firstModel = HMMFromMatrices(sigma, DiscreteDistribution(sigma), A, B, pi)
	print 'Untrained Model: '+str(firstModel)
	model = trainModel(firstModel, dictionary, pathToGoodware, fixedLength, sigma)
	return model, sigma

def initParams(lenDictionary):
	sigma = IntegerRange(0, lenDictionary)	
	A = [[0.5, 0.5], [0.5, 0.5]]
	# equal distribution for each possible observation, which can be found in the dictionary
	emisBenign = [1.0 / lenDictionary] * lenDictionary
	emisMal = [1.0 / lenDictionary] * lenDictionary
	B = [emisBenign, emisMal]
	pi = [1.0, 0.0]	
	return sigma, A, B, pi

def trainModel(model, dictionary, pathToGoodware, fixedLength, sigma):
	print 'Training model for fixed length '+str(fixedLength)+' ...'
	benignSamples = getTrainingSamples(dictionary, pathToGoodware, fixedLength)
	seqSet = SequenceSet(sigma, benignSamples)
	model.baumWelch(seqSet, 10000000)
	print 'Trained Model: '+str(model)
	return model

def getTrainingSamples(dictionary, path, fixedLength):
	position = 0
	amount = 10
	numberOfFiles = jsonf.getNumberOfFilesInFolder(path)
	allSamples = []
	# load training samples in packages of 10 in order to ensure a smooth execution
	for i in range(0, (numberOfFiles/amount)+1):
		samples, paths = getAmountOfData(dictionary, path, position, amount, fixedLength)
		allSamples.extend(samples)
		position = position + amount
	return allSamples

def computeAllLogs(modelsArray, pathDataToClassify, outputPath, pathToDictionary, fixedLengthArray, isBenignData):
	"""
	Compute the log-likelihood of input traces to be generated by the trained model, regarding different fixed lengths for the traces
	:param modelsArray: list of hidden markov models and the domain of the observations for each fixed length
	:param pathDataToClassify: path to folder that contains the traces that will be classified
	:param outputPath: path to folder, in which the resulting file will be stored
	:param pathToDictionary: path to the dictionary file that contains the method names of all API calls 
	:param fixedLengthArray: list of lengths to which the samples are fixed
	:param isBenignData: label if the data is benign or malicious
	:type modelsArray: list
	:type pathDataToClassify: string
	:type outputPath: string
	:type pathToDictionary: string
	:type fixedLengthArray: list
	:type isBenignData: boolean
	"""
	for i in range(len(fixedLengthArray)):
		computeLogsFixedLength(modelsArray[i], pathDataToClassify, outputPath, pathToDictionary, fixedLengthArray[i], isBenignData)

def computeLogsFixedLength(modelAndSigma, pathDataToClassify, outputPath, pathToDictionary, fixedLength, isBenignData):
	outputPathLog, outputPathLogWithPath, outputPathCountSamples = getOutputPaths(isBenignData, outputPath, fixedLength)
	model = modelAndSigma[0]
	sigma = modelAndSigma[1]
	dictionary = dictMeth.getMethodDictionary(pathToDictionary)
	log, logAndPath, countSamples = calculateLog(dictionary, pathDataToClassify, model, sigma, fixedLength)
	# write classification results to files
	system.writeNumberOfFiles(outputPathCountSamples, countSamples, fixedLength, isBenignData)
	jsonf.write(outputPathLog, log)
	jsonf.write(outputPathLogWithPath, logAndPath)

def getOutputPaths(isBenignData, outputPath, fixedLength):
	outputPathCountSamples = outputPath+'filesAtLength.txt'
	outputPathLog, outputPathLogWithPath = '',''
	if isBenignData:
		outputPathLog = outputPath+'logBenign_'+str(fixedLength)+'.txt'
		outputPathLogWithPath = outputPath+'logBenignWithPath_'+str(fixedLength)+'.txt'
	else:
		outputPathLog = outputPath+'logMalicious_'+str(fixedLength)+'.txt'
		outputPathLogWithPath = outputPath+'logMaliciousWithPath_'+str(fixedLength)+'.txt' 
	return outputPathLog, outputPathLogWithPath, outputPathCountSamples

def calculateLog(dictionary, path, model, sigma, fixedLength):
	counter = 0
	amount = 10
	numberOfFiles = jsonf.getNumberOfFilesInFolder(path)
	allLogs, allLogsAndPaths = [], []
	countSamplesWithLength = 0
	# calculate log-likelihood of traces in packages of 10 in order to ensure a smooth execution
	for i in range(0, (numberOfFiles/amount)+1):
		log, logAndPath, counter, countSamplesWithLength = getLogs(dictionary, path, counter, amount, fixedLength, model, sigma, countSamplesWithLength)
		allLogs.extend(log)
		allLogsAndPaths.extend(logAndPath)
	return allLogs, allLogsAndPaths, countSamplesWithLength

def getLogs(dictionary, path, counter, amount, fixedLength, model, sigma, countSamplesWithLength):
	samples, samplePaths = getAmountOfData(dictionary, path, counter, amount, fixedLength)
	log, logAndPath = computeLogForAmountOfSamples(model, sigma, samples, samplePaths)
	# update the number of samples found with the fixed length and increase the counter by the amount of 10
	countSamplesWithLength = countSamplesWithLength + len(samples)
	counter = counter+amount
	return log, logAndPath, counter, countSamplesWithLength

def getAmountOfData(dictionary, path, position, amount, fixedLength):
	data, fileNames = jsonf.getAmountOfFilesInFolder(path, position, amount)
	allSamples, samplePaths = createAllSamples(data, dictionary, fixedLength, fileNames)
	return allSamples, samplePaths

def createAllSamples(data, dictionary, fixedLength, fileNames):
	allSamples, samplePaths = [], []
	for i in range(len(data)):
		sample = createSampleFromData(data[i], dictionary)
		# only add samples of length 'fixedLength', discard those which are smaller
		if len(sample) < fixedLength:
			continue
		else:
			allSamples.append(sample[0:fixedLength])
			samplePaths.append(fileNames[i])
	return allSamples, samplePaths
	
def createSampleFromData(data, dictionary):
	sample = []
	methods = jsonf.getAllMethods(data)
	# convert the method names of the sample into numerical values
	for j in range(len(methods)):
		slicedMethod = dictMeth.sliceMethod(methods[j])
		sample.append(dictionary[slicedMethod])
	return sample

def computeLogForAmountOfSamples(model, sigma, data, samplePaths):
	allLogs, logsAndPaths = [], []
	for i in range(len(data)):
		log = computeLogForOneSample(model, sigma, data[i])
		allLogs.append(log)
		logsAndPaths.append([log, samplePaths[i]])
	return allLogs, logsAndPaths

def computeLogForOneSample(model, sigma, sample):
	"""
	Compute log-likelihood value for a single trace given a trained model with the tool 'GHMM'
	:param model: trained Hidden Markov Model
	:param sigma: domain of observations
	:param sample: trace of API calls, for which the log-likelihood will be calculated
	:type model: ghmm.DiscreteEmissionHMM
	:type sigma: ghmm.Alphabet
	:type sample: list
	:return: calculated log-likelihood value
	:rtype: int
	"""
	log = model.loglikelihood(EmissionSequence(sigma, sample))
	# convert minus infinity to the int value '-100000' in order to enable a smooth subsequent processing
	if log == -float('Inf'):
		log = -100000
	return log

def getThresholdsForEachLength(data, thrEnd):
	lengths = data[0]
	thresholdsAndLength = []
	# for each length find the threshold that has the highest accuracy value
	for i in range(1, len(lengths)):
		highestAccuracy, threshold = getHighestAccuracy(data, i)
		# add the threshold with the highest accuracy to the results except when the last threshold is reached and the accuracy is not high enough
		if not (threshold == thrEnd and highestAccuracy < 0.85):	
			thresholdsAndLength.append([threshold, int(lengths[i])])
	return thresholdsAndLength

def getHighestAccuracy(data, index):
	highestAccuracy = 0.0
	threshold = 0
	for j in range(1, len(data)):
		accuracy = getAccuracyFromString(data[j][index])
		# if two or more thresholds have the same accuracy the smaller one is chosen, because it has a higher specificity
		if accuracy >= highestAccuracy:
			highestAccuracy = accuracy
			threshold = int(data[j][0])
	return highestAccuracy, threshold

def getAccuracyFromString(string):
	accuracy = string.rsplit('/', 1)[1]
	return float(accuracy)

def getMediumThresholds(allThresholds):
	thresholdsAndLengths = []
	changedAxis = [[j for j in elements if j is not None] for elements in  list(izip_longest(*allThresholds))]
	# for each length the middle element of the thresholds is calcualted
	for i in range(len(changedAxis)):
		length = changedAxis[i][0][1]
		thresholds = getThresholds(changedAxis[i])
		sortedThr = sorted(thresholds)
		middleElement = sortedThr[len(sortedThr)/2]
		thresholdsAndLengths.append([middleElement, length])
	return thresholdsAndLengths

def getThresholds(element):
	thresholds = []
	for j in range(len(element)):
		thresholds.append(element[j][0])
	return thresholds
