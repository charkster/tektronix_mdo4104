#!/usr/bin/python
import datetime
import os

class tektronix_mdo4104():

    # Constructor
    def __init__(self, pyvisa_instr, timeout=10000, debug=False):
        self.scope         = pyvisa_instr  # this is the pyvisa instrument
        self.scope.timeout = timeout       # this is in milliseconds and needed for screen capture
        self.debug         = debug

    meas_type_list = ['AMPLITUDE',   'AREA',    'BURST',     'CAREA',      'CMEAN',       'CRMS',
                      'DELAY',       'FALL',    'FREQUENCY', 'HIGH,HITS',  'LOW,MAXIMUM', 'MEAN',
                      'MEDIAN',      'MINIMUM', 'NDUTY',     'NEDGECOUNT', 'NOVERSHOO',
                      'NPULSECOUNT', 'NWIDTH',  'PEAKHITS',  'PDUTY',      'PEDGECOUNT',
                      'PERIOD',      'PHASE',   'PK2PK',     'POVERSHOOT', 'PPULSECOUNT', 'PWIDTH',
                      'RISE',        'RMS',     'SIGMA1',    'SIGMA2',     'SIGMA3',      'STDDEV',
                      'WAVEFORMS']

    meas_slot_list = [1, 2, 3, 4, 5, 6, 7, 8]

    channel_list = ['CH1', 'CH2',  'CH3', 'CH4',
                    'D0',  'D1',   'D2',  'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'D11', 'D12', 'D13', 'D14', 'D15',
                    'EXT', 'LINE', 'AUX']

    def get_analog_channel_setup(self):
        result_dict = {}
        for channel in [1, 2, 3, 4]:
            if (self.scope.query('sel:CH{0}?'.format(channel)).rstrip('\n') == '1'):
                label     = self.scope.query('CH{0}:LABel?'.format(channel)).rstrip('\n').replace('"','')
                scale     = float(self.scope.query('CH{0}:SCAle?'.format(channel)).rstrip('\n'))
                offset    = float(self.scope.query('CH{0}:OFFSet?'.format(channel)).rstrip('\n'))
                bandwidth = float(self.scope.query('CH{0}:BANdwidth?'.format(channel)).rstrip('\n'))
                coupling  = self.scope.query('CH{0}:COUPling?'.format(channel)).rstrip('\n')
                result_dict[channel] = (label, scale, offset, bandwidth, coupling)
        return result_dict

    def set_analog_channel_setup(self, analog_ch_dict={}):
        ch_desc = {
            'label'     : 0,
            'ver_scale' : 1,
            'ver_offset': 2,
            'bw'        : 3,  # 20E6, 250E6, 'FULl'
            'coupling'  : 4,  # 'AC', 'DC', 'DCREJect'
        }
        for k, v in analog_ch_dict.items():
            self.scope.write('sel:CH{0} on'.format(k))
            self.scope.write('CH{0}:LABel "{1}"'.format(k, v[ch_desc['label']]))
            self.scope.write('CH{0}:SCAle {1}'.format(k, v[ch_desc['ver_scale']]))
            self.scope.write('CH{0}:OFFSet {1}'.format(k, v[ch_desc['ver_offset']]))
            self.scope.write('CH{0}:BANdwidth {1}'.format(k, v[ch_desc['bw']]))
            self.scope.write('CH{0}:COUPling {1}'.format(k, v[ch_desc['coupling']]))


    def get_digital_channel_setup(self):
        result_dict = {}
        for channel in range(0,16):
            if (self.scope.query('sel:D{0}?'.format(channel)).rstrip('\n') == '1'):
                label = self.scope.query('D{0}:LABel?'.format(channel)).rstrip('\n').replace('"','')
                result_dict[channel] = label
        return result_dict

    def set_digital_channel_setup(self, digital_ch_dict={}):
        for key in digital_ch_dict.keys():
            self.scope.write('sel:D{0} on'.format(key))
            self.scope.write('D{0}:LABel "{1}"'.format(key,digital_ch_dict[key]))

    def channel_setup(self, analog_ch_dict={}, digital_ch_dict={}, math_ch_dict={}):
        """
        This adjusts the analog channels of the Tek scope, based on the parameters received.
        :param analog_ch_dict: A dictionary that lists all the parameters for the channels. Key is the channel number.
            Values are in this order: label, vertical scale, vertical offset, bandwidth [for voltage probes: '20E6', 'FULl']
        :return: None

        Example:
            # - label, ver_scale, ver_offset (voltage value not divisions, with center line as 0V), bw, coupling
            analog_channels = {
                1: ('VSIG_1', 0.5,   0, '20E6', 'DC'),
                2: ('ISIG_2', 0.5,   1, 'FULl', 'DC'),
                3: ('V_3',    1.0, 0.2, '20E6', 'DC'),
                4: ('VDD_4',  0.5, 1.0, '20E6', 'DC')
            }

            # --- DIGITAL CHANNELS ---
            # key: digital channel; value: channel label
            digital_channels = {
                0: 'dig_sig1',
                1: 'dig_sig2'
            }

            #--- MATH CHANNEL ---
            # valid math operations are +, -, *, /
            # - label, operator, source1, source2, vertical scale, vertical center
            math_channels = {
                0: ('V1-V2', '-', 'C1', 'C2', 1.00, 0.5)
            }

        """
        ch_desc = {
            'label':      0,
            'ver_scale':  1,
            'ver_offset': 2,
            'bw':         3,  # 20E6, 250E6, 'FULl'
            'coupling':   4,  # 'AC', 'DC', 'DCREJect'
        }

        math_ch_desc = {
            'label':      0,
            'operator':   1,  # 'Difference'
            'source1':    2,  # 'CH1' <--- TEKTRONIX needs the CH, Lecroy just uses C
            'source2':    3,  # 'CH2' <--- TEKTRONIX needs the CH, Lecroy just uses C
            'ver_scale':  4,
            'ver_center': 5,
        }

        if (self.scope.query("*IDN?").startswith("TEKTRONIX,MDO4104B-6") and len(analog_ch_dict) > 4):
            print("ERROR!!! scope is MDO4104, and more than 4 analog channels are specified")
            return -1

        # ***** Analog Channel Section ******************************************************************
        # --- Turn off all analog channels ---
        for sweep_channels in range(1, 5):
            self.scope.write('sel:CH{0} off'.format(sweep_channels))

        # --- Turn on all listed analog channels and set up ---
        for k, v in analog_ch_dict.items():
            self.scope.write('sel:CH{0} on'.format(k))
            self.scope.write('CH{0}:LABel "{1}"'.format(k, v[ch_desc['label']]))
            self.scope.write('CH{0}:SCAle {1}'.format(k, v[ch_desc['ver_scale']]))
            self.scope.write('CH{0}:OFFSet {1}'.format(k, v[ch_desc['ver_offset']]))
            self.scope.write('CH{0}:BANdwidth {1}'.format(k, v[ch_desc['bw']]))
            self.scope.write('CH{0}:COUPling {1}'.format(k, v[ch_desc['coupling']]))
        # ***** End Analog Channel Section **************************************************************

        # ***** Digital Channel Section ******************************************************************
        for sweep_dig_channels in range(0, 15):
            self.scope.write('sel:D{0} off'.format(k))

        for k, v in digital_ch_dict.items():
            self.scope.write('sel:D{0} on'.format(k))
            self.scope.write('D{0}:LABel "{1}"'.format(k, v))
        # ***** End Digital Channel Section **************************************************************

        # ***** Math Channel Section ******************************************************************
        # Disable math channel
        self.scope.write('sel:MATH off')
        # --- Turn on listed math channels ---
        for k, v in math_ch_dict.items():
            self.scope.write('sel:MATH on')
            self.scope.write('MATH:LABEL "{0}"'.format(v[math_ch_desc['label']]))
            self.scope.write('MATH:TYPE DUAL') # assume dual for now, if Source2 is not defined then we could do something different
            print('MATH:DEFINE "{0}{1}{2}"'.format(v[math_ch_desc['source1']], v[math_ch_desc['operator']], v[math_ch_desc['source2']]))
            self.scope.write('MATH:DEFINE "{0}{1}{2}"'.format(v[math_ch_desc['source1']], v[math_ch_desc['operator']], v[math_ch_desc['source2']]))
            self.scope.write('MATH:VERICAL:POSITION {0}'.format(v[math_ch_desc['ver_center']]))
            self.scope.write('MATH:VERICAL:SCALE {0}'.format(v[math_ch_desc['ver_scale']]))
        # ***** End math Channel Section **************************************************************

    def get_horizontal_scale(self):
        return float(self.scope.query('HOR:SCA?').rstrip('\n'))

    def set_horizontal_scale(self, scale=1E-3):
        self.scope.write('HOR:SCA %e' % scale)

    def get_trigger_setup(self):
        trigger_list = []
        trigger_list.append(self.scope.query('TRIG:A:EDGE:SOUrce?').rstrip())
        trigger_list.append(self.scope.query('TRIG:A:TYPE?').rstrip())
        trigger_list.append(float(self.scope.query('TRIG:A:LEVEL?').rstrip()))
        trigger_list.append(float(self.scope.query('HOR:DEL:TIME?').rstrip()))
        trigger_list.append(self.scope.query('TRIG:A:EDGE:SLOPE?').rstrip())
        trigger_list.append(self.scope.query('TRIG:A:MOD?').rstrip())
        return trigger_list

    def set_trigger_setup(self,trigger_list=[]):
        self.scope.write('TRIG:A:EDGE:SOUrce {0}'.format(trigger_list[0]))
        self.scope.write('TRIG:A:TYPE {0}'.format(trigger_list[1]))
        self.scope.write('TRIG:A:LEVEL {0}'.format(trigger_list[2]))
        self.scope.write('HOR:DEL:TIME {0}'.format(trigger_list[3]))
        self.scope.write('TRIG:A:EDGE:SLOPE {0}'.format(trigger_list[4]))
        self.scope.write('TRIG:A:MOD {0}'.format(trigger_list[5]))


    def rf_channel_setup(self, rf_setting_list):
        """
         This adjusts the RF channel of the Tek scope, based on the parameters received.
         :param rf_setting_list: A list with all the parameters for the RF channel.
             Values are in this order: ref, scale, center frequency, span and rbw
         :return: None

         Example:
             # ref, scale, start, stop and rbw
             rf_setting_list = [ -10.0, 10.0, 100E3, 4.0E6, 1.0E3 ]
             }
         """
        ch_desc = { 'ref'    : 0, # -10.0 (dB)
                    'scale'  : 1, #  10.0 (dB/div)
                    'start'  : 2, #  100E3  (Hz)
                    'stop'   : 3, #  4.0E5  (Hz)
                    'rbw'    : 4, #  2.0E3  (Hz)
        }

        self.scope.write('SELect:RF_NORMAL ON') # Turn RF channel on
        self.scope.write('RF:REFLevel {0}'.format(rf_setting_list[ch_desc['ref']]))
        self.scope.write('RF:SCAle {0}'.format(rf_setting_list[ch_desc['scale']]))
        self.scope.write('RF:STARt {0}'.format(rf_setting_list[ch_desc['start']]))
        self.scope.write('RF:STOP {0}'.format(rf_setting_list[ch_desc['stop']]))
        self.scope.write('RF:RBW:MODe MANual')
        self.scope.write('RF:RBW {0}'.format(rf_setting_list[ch_desc['rbw']]))
#        self.scope.write('MARKER:MANual ON')

    def get_screen_image(self, path_with_filename='', backcolor='WHITE'):
        # valid backcolor can be either 'WHITE' or 'BLACK'
        # example: get_screen_image(path_with_filename='C:/temp/python/tek2.png')
        # you must have a usb drive inserted if there is no local disk on the scope!!

        if (backcolor == 'WHITE'):
            self.scope.write('SAVe:IMAGe:INKSaver ON')
        else:
            self.scope.write('SAVe:IMAGe:INKSaver OFF')
        self.scope.write("SAVe:IMAGe:FILEFormat PNG")
        self.scope.write("HARDCopy STARt")
        raw_data = self.scope.read_raw(1024*1024)
        if (path_with_filename == ''):
            path_with_filename = "C:\\temp\python\\tek_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        elif '.png' not in path_with_filename:  # append png if not given
            path_with_filename += '.png'
        file_stream = open(path_with_filename, 'wb')
        file_stream.write(raw_data)
        file_stream.close()
        return len(raw_data)

    def get_channel_settings(self, path_with_filename='', channel='RF_NORMal'):
        # valid channels include 'CH1' -> 'CH4', 'D1' -> 'D15', 'RF_NORMAL'
        self.scope.write('DATa:SOUrce %s' % channel)
        self.scope.write('DATa:ENCdg ASCIi')
        self.scope.write('DATa:WIDth 2')
        self.scope.query('WFMPRE:XINCR') #this looks odd, but is needed
        self.scope.write('CURVe?')
        raw_data = self.scope.read_raw()
        if (path_with_filename == ''):
            path_with_filename = "tek_wfm_data_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        elif '.txt' not in path_with_filename:  # append png if not given
            path_with_filename += '.txt'
        file_stream = open(path_with_filename, 'wb')
        file_stream.write(raw_data)
        file_stream.close()
        return len(raw_data)

    def get_channel_waveform_data(self, path_with_filename='', channel='RF_NORMal', width=2, append=0, append_corners=''):
        self.scope.write('DATa:SOUrce %s' % channel)
        self.scope.write('DATa:WIDth %d' % width)
        self.scope.write('DATa:STARt 1')
        self.scope.write('DATa:STARt 20000') # more points than what is available, on purpose
        self.scope.write('DATa:ENCdg ASCIi')
        self.scope.write('HEADer 1')
        self.scope.write('VERBose')
        self.scope.query('WFMOutpre?')
        self.scope.write('HEADer 0')

        if (channel == 'RF_NORMal'):
            ref_level = float(self.scope.query('RF:REFLevel?'))
            # if ref_level is negative, we need to gain the waveform data to look like the oscilloscope
            gain = 10 ** ((-1.0 * ref_level)/10)
            print("gain to be applied to waveform data is %g" % gain)

        self.scope.write('CURVe?')
        raw_data = self.scope.read_raw()

        if (path_with_filename == ''):
            path_with_filename = "tek_wfm_data_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        elif '.txt' not in path_with_filename:  # append png if not given
            path_with_filename += '.txt'
        if (append == 1) and os.path.exists(path_with_filename):
            file_stream = open(path_with_filename, 'a')
        else:
            file_stream = open(path_with_filename, 'w')
        if (append == 1):
            file_stream.write(append_corners)
        file_stream.write(raw_data)
        file_stream.close()
        return len(raw_data)

    def measure_no_display(self, channel='CH1', type='FREQUENCY'):
        # this will just perform a measurement without displaying it on the screen
        if (type not in self.meas_type_list):
            print("Invalid measurement type")
            return -1
        elif (channel not in self.channel_list):
            print("Invalid channel")
            return -1
        else:
            self.scope.write('MEASU:IMM:SOU1 %s' % channel)
            self.scope.write('MEASU:IMM:TYPE %s' % type)
            result = float(self.scope.query("MEASU:IMM:VAL?"))
            return result

    def measure_with_display(self, slot=1, channel='CH1', type='FREQUENCY'):
        # this will configure a measurement and display it on the screen
        if (type not in self.meas_type_list):
            print("Invalid measurement type")
            return -1
        elif (slot not in self.meas_slot_list):
            print("Invalid slot")
            return -1
        else:
            self.scope.write('MEASUrement:MEAS%d:SOUrce%d %s' % (slot ,1, channel)) # single source measurement
            self.scope.write('MEASUrement:MEAS%s:TYPe %s'   % (slot, type))
            self.scope.write('MEASUrement:MEAS%d:STATE ON' % slot)

