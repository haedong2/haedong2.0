# -*- coding: utf-8 -*-
import sys
import threading
import time

from PyQt5 import QAxContainer, QtWidgets
from modules import auto_login, close_popup, __module
from manager import chart_manager, contract_manager, strategy_manager
from constant import screen, const
from var import subject
# from var import *
from utils import util


class Api(__module.ModuleClass):
    req = []
    input_value = []
    last_req_time = time.time()
    last_pwd_check_time = time.time()
    app = None
    account_pwd_input = False
    account = ""
    누적수익 = 0
    subject_code = ''

    strategy_var = None
    subject_var = None

    contract_manager = None
    chart_manager = None
    strategy_manager = None
    
    def __init__(self, _stv=None):
        super(Api, self).__init__()

        self.subject_var = subject.Subject()

        # Headong Manager Set-up
        self.contract_manager = contract_manager.ContractManager()
        self.chart_manager = chart_manager.ChartManger(_stv, self.subject_var)
        self.strategy_manager = strategy_manager.StrategyManager(self.subject_var)

        if const.MODE is const.REAL:
            # Kiwoom set-up
            self.log.info("해동이2.0 실제투자 시작 합니다.")
            self.app = QtWidgets.QApplication(sys.argv)
            self.ocx = QAxContainer.QAxWidget("KFOPENAPI.KFOpenAPICtrl.1")
            self.ocx.OnEventConnect[int].connect(self.OnEventConnect)
            self.ocx.OnReceiveTrData[str, str, str, str, str].connect(self.OnReceiveTrData)
            self.ocx.OnReceiveChejanData[str, int, str].connect(self.OnReceiveChejanData)
            self.ocx.OnReceiveRealData[str, str, str].connect(self.OnReceiveRealData)

            # Overall Configuration Values
            self.strategy_var = self.strategy_manager.get_strategy_var_from_config()

            if self.connect == 0:
                self.app.exec_()

        elif const.MODE is const.TEST:
            self.strategy_var = _stv
            self.chart_manager.set_stv(self.strategy_var)

        else:
            self.log.debug("MODE:"+str(const.MODE))

        self.log.info("Headong API 종료")
            
    '''
    Interface Methods
    '''
    @property
    def connect(self):
        """
        로그인 윈도우를 실행한다.
        로그인이 성공하거나 실패하는 경우 OnEventConnect 이벤트가 발생하고 이벤트의 인자 값으로 로그인 성공 여부를 알 수 있다.

        :return: 0 - 성공, 음수값은 실패
        """

        if self.ocx.dynamicCall("GetConnectState()") == 0:
            rtn = self.ocx.dynamicCall("CommConnect(1)")
            if rtn == 0:
                self.log.debug("연결 성공")

                # auto login
                auto_login.Login().start()

            else:
                self.log.debug("연결 실패")

            return rtn

    def get_login_info(self, sTag):
        """
        로그인한 사용자 정보를 반환한다.

        :param sTag: 사용자 정보 구분 TAG값
            “ACCOUNT_CNT” ? 전체 계좌 개수를 반환한다.
            "ACCNO" ? 전체 계좌를 반환한다. 계좌별 구분은 ‘;’이다.
            “USER_ID” - 사용자 ID를 반환한다.
            “USER_NAME” ? 사용자명을 반환한다.
            “KEY_BSECGB” ? 키보드보안 해지여부. 0:정상, 1:해지
            “FIREW_SECGB” ? 방화벽 설정 여부. 0:미설정, 1:설정, 2:해지
            Ex) openApi.GetLoginInfo(“ACCOUNT_CNT”);
        :return: TAG값에 따른 데이터 반환
        """
        return self.ocx.dynamicCall("GetLoginInfo(QString)", [sTag]).rstrip(';')

    def get_dynamic_subject_code(self):
        lists = ['MTL', 'ENG', 'CUR', 'IDX', 'CMD']
        for code in lists:
            self.set_input_value("상품코드", code)
            self.comm_rq_data("상품별현재가조회", "opt10006", "", screen.S0010)

    def get_dynamic_subject_market_time(self):
        lists = ['MTL', 'ENG', 'CUR', 'IDX', 'CMD']
        for list_ in lists:
            self.set_input_value("품목구분", list_)
            self.comm_rq_data("장운영정보조회", "opw50001", "", screen.S0011)

    def get_contract_list(self):
        self.set_input_value("계좌번호", self.account)
        self.set_input_value("비밀번호", "")
        self.set_input_value("비밀번호입력매체", "00")
        self.set_input_value("통화코드", "")
        self.comm_rq_data("미결제잔고내역조회", "opw30003", "", screen.S0012)

    def get_my_deposit_info(self):
        self.set_input_value("계좌번호", self.account)
        self.set_input_value("비밀번호", "")
        self.set_input_value("비밀번호입력매체", "00")
        self.comm_rq_data("예수금및증거금현황조회", "opw30009", "", screen.S0011)

    def get_futures_deposit(self):
        lists = ['MTL', 'ENG', 'CUR', 'IDX', 'CMD']
        today = util.get_today_date()
        for list_ in lists:
            self.set_input_value("품목구분", list_)
            self.set_input_value("적용일자", today)
            self.comm_rq_data("상품별증거금조회", "opw20004", "", screen.S0011)

    def send_order(self, contract_type, subject_code, contract_cnt):

        """
        주식 주문을 서버로 전송한다.
        신규매수:self.send_order("신규매수","0101",my_account_number,1,subject_code,1,now_current_price,"","2","")


        신규매도:
        매수청산:
       매도청산:self.send_order("신규매수","0101",my_account_number,2,subject_code,subject_info[subject_code]['보유수량'],now_current_price,"2","")


        :return:
        :type contract_type: object
        :type subject_code: object
        :type contract_cnt: object
        :param sRQName: 사용자 구분 요청 명
        :param sScreenNo: 화면번호[ㄱ4]
        :param sAccNo: 계좌번호[10]
        :param nOrderType: 주문유형 (1:신규매수, 2:신규매도, 3:매수취소, 4:매도취소, 5:매수정정, 6:매 도정정)
        :param sCode: 주식종목코드
        :param nQty: 주문수량
        :param sPrice: 주문단가
        :param sStop: 스탑단가
        :param sHogaGb: 거래구분 1:시장가, 2:지정가, 3:STOP, 4:STOP LIMIT

            ※ 시장가, 최유리지정가, 최우선지정가, 시장가IOC, 최유리IOC, 시장가FOK, 최유리FOK, 장전시간외, 장후시간외 주문시 주문가격을 입력하지 않습니다.
            ex)
            지정가 매수 - openApi.SendOrder(“RQ_1”, “0101”, “5015123410”, 1, “000660”, 10, 48500, “00”, “”);
            시장가 매수 - openApi.SendOrder(“RQ_1”, “0101”, “5015123410”, 1, “000660”, 10, 0, “03”, “”);
            매수 정정 - openApi.SendOrder(“RQ_1”,“0101”, “5015123410”, 5, “000660”, 10, 49500, “00”, “1”);
            매수 취소 - openApi.SendOrder(“RQ_1”, “0101”, “5015123410”, 3, “000660”, 10, 0, “00”, “2”);
        :param sOrgOrderNo: 원주문번호
        :return: 에러코드 - parse_error_code
            -201     : 주문과부하
            -300     : 주문입력값 오류
            -301     : 계좌비밀번호를 입력하십시오.
            -302     : 타인 계좌를 사용할 수 없습니다.
            -303     : 경고-주문수량 200개 초과
            -304     : 제한-주문수량 400개 초과

        """
        _contract_type = 0
        if contract_type == '신규매수':
            _contract_type = 2
        elif contract_type == '신규매도':
            _contract_type = 1
        else:
            return -300

        if const.MODE is const.REAL:
            return self.ocx.dynamicCall(
                "SendOrder(QString, QString, QString, int, QString, int, QString, QString, QString, QString)",
                [contract_type, '0101', self.account, _contract_type, subject_code, contract_cnt, '0', '0', '1', ''])
        elif const.MODE is const.TEST: # 테스트
            # tester.send_order(contract_type, subject_code, contract_cnt, '1')
            return 0

    def request_tick_info(self, subject_code, tick_unit, prevNext):

        self.set_input_value("종목코드", subject_code)
        self.set_input_value("시간단위", tick_unit)

        rqTag = "해외선물옵션틱차트조회" + "_" + subject_code + "_" + tick_unit

        self.comm_rq_data(rqTag, "opc10001", prevNext, self.subject_var.info[subject_code]['화면번호'])

    def request_min_info(self, subject_code, tick_unit, prevNext):

        self.set_input_value("종목코드", subject_code)
        self.set_input_value("시간단위", tick_unit)

        rqTag = "해외선물옵션분차트조회" + "_" + subject_code + "_" + tick_unit
        self.comm_rq_data(rqTag, "opc10002", prevNext, self.subject_var.info[subject_code]['화면번호'])

    def send_request(self):
        if len(self.req) > 0:
            config = self.req[0]
            self.log.debug("send_request(), config : %s" % config)
            # log.debug("current thread : %s" % threading.current_thread().__class__.__name__)
            for input_value in config["InputValue"]:
                # log.debug("set input value, id : %s, value : %s" % (input_value[0], input_value[1]))
                self.ocx.dynamicCall("SetInputValue(QString, QString)", input_value[0], input_value[1])

            rtn = self.ocx.dynamicCall("CommRqData(QString, QString, QString, QString)", config['sRQName'],
                                       config['sTrCode'], config['nPrevNext'], config['sScreenNo'])
            # log.debug("send_request(), rtn value : %s" % rtn)

            if rtn == 0:
                del self.req[0]

                # debug code
                if len(self.req) > 0:
                    time.sleep(0.25)
                    self.send_request()
                    self.last_req_time = time.time()
            else:
                self.err_log.error('send request() : %s' % util.parse_error_code(rtn))

    def set_input_value(self, sID, sValue):
        """
        Tran 입력 값을 서버통신 전에 입력한다.

        :param sID: 아이템명
        :param sValue: 입력 값
        Ex) openApi.SetInputValue(“종목코드”, “000660”);
            openApi.SetInputValue(“계좌번호”, “5015123401”);
        """
        try:
            self.log.debug("set_input_value(), sID: %s, sValue: %s" % (sID, sValue))
            # rq_thread.set_input_value(sID, sValue)
            self.input_value.append([sID, sValue])
        except Exception as err:
            self.log.error(util.get_error_msg(err))

    def comm_rq_data(self, sRQName, sTrCode, nPrevNext, sScreenNo):
        """
        Tran을 서버로 송신한다.

        :param sRQName: 사용자구분 명
        :param sTrCode: Tran명 입력
        :param nPrevNext: 0:조회, 2:연속
        :param sScreenNo: 4자리의 화면번호
        Ex) openApi.CommRqData( “RQ_1”, “OPT00001”, 0, “0101”);
        :return:
        OP_ERR_SISE_OVERFLOW – 과도한 시세조회로 인한 통신불가
        OP_ERR_RQ_STRUCT_FAIL – 입력 구조체 생성 실패
        OP_ERR_RQ_STRING_FAIL – 요청전문 작성 실패
        OP_ERR_NONE(0) – 정상처리
        """
        try:
            self.log.debug("comm_rq_data(), sRQName: %s, sTrCode: %s, nPrevNext: %s, sScreenNo: %s"
                           % (sRQName, sTrCode, nPrevNext, sScreenNo))
            request_config = {"InputValue": self.input_value,
                              "sRQName": sRQName,
                              "sTrCode": sTrCode,
                              "nPrevNext": nPrevNext,
                              "sScreenNo": sScreenNo}

            self.input_value = []
            self.req.append(request_config)

            now = time.localtime()
            if const.MODE == const.REAL and \
                    ((now.tm_wday == 5 and util.get_time(0, None) > 600) or (now.tm_wday == 6)):
                time.sleep(0.25)
                self.send_request()

        except Exception as err:
            self.log.error(util.get_error_msg(err))

    def quit(self, nErrCode):
        """ Quit the server """
        result = None
        if nErrCode == 0:
            result = str('Kiwoom API 종료 상태[%s]' % util.parse_error_code(nErrCode))
            self.log.info(result)
             
        elif nErrCode == -106:
            result = str('Kiwoom API 종료 상태[%s]' % util.parse_error_code(nErrCode))
            
            # 팝업 종료 필요
            self.err_log.error(result)
            self.app.quit()
            self.log.info("4초 후 팝업 종료")
            close_popup.ClosePopup(4).start()
            
        else:
            result = str('에러 상태 체크 필요[%s]' % util.parse_error_code(nErrCode))
            self.err_log.error(result)

    '''
    Control Event Handlers
    '''
    def OnEventConnect(self, nErrCode):
        """
        통신 연결 상태 변경시 이벤트

        :param nErrCode: 에러 코드 - 0이면 로그인 성공, 음수면 실패, 에러코드 참조
        """
        self.log.debug("OnEventConnect received")

        if nErrCode == 0:
            self.log.debug("로그인 성공")
            # 계좌번호 저장
            self.account = self.get_login_info("ACCNO")
            self.telepot.set_account(self.account)
            self.telepot.send_message('해동이 정상 시작 됨.')
            self.log.debug("계좌번호 : " + self.account)

            if const.MODE is const.REAL:
                # 다이나믹 종목 정보 요청
                self.get_dynamic_subject_code()
                self.get_futures_deposit()
                # self.get_my_deposit_info()

                # 종목 정보 로그 찍기
                self.log.debug("참여 종목 : %s" % self.subject_var.info.values())

            self.send_request()

        elif nErrCode == -101:
            # wait_time = (06:45).to_sec() - time.time()
            # time.sleep(wait_time)
            # const.MODE = const.DB_INSERT
            # DB INSERT CODE
            self.quit(nErrCode)
        
        elif nErrCode == -106:
            # Kiwoom API 종료 상태
            self.quit(nErrCode)

        else:
            # 로그인 실패 로그 표시 및 에러코드별 에러내용 발송
            self.quit(nErrCode)

    def OnReceiveTrData(self, sScrNo, sRQName, sTrCode, sRecordName, sPreNext, candle=None):
        """
        Tran 수신시 이벤트
        서버통신 후 데이터를 받은 시점을 알려준다.

        :param py: 화면번호
        :param sRQName: 사용자구분 명
        :param sTrCode: Tran 명
        :param sRecordName: Record 명
        :param sPreNext: 연속조회 유무
        :param nDataLength: 1.0.0.1 버전 이후 사용하지 않음.
        :param sErrorCode: 1.0.0.1 버전 이후 사용하지 않음.
        :param sMessage: 1.0.0.1 버전 이후 사용하지 않음.
        :param sSplmMsg: 1.0.0.1 버전 이후 사용하지 않음.
        """
        self.log.debug("current thread : %s" % threading.current_thread().__class__.__name__)
        self.log.debug("onReceiveTrData, sScrNo : %s, sRQName : %s, sTrCode : %s, sRecordName : %s, sPreNext : %s" % (sScrNo, sRQName, sTrCode, sRecordName, sPreNext))

        try:
            if sRQName == '상품별현재가조회':
                self.log.debug("onRecieveTrData: 상품별현재가조회")
                for i in range(20):
                    subject_code = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                        sRecordName, i, '종목코드n').strip()  # 현재가 = 틱의 종가
                    subject_symbol = subject_code[:2]
                    self.log.debug("상품별현재가조회, 종목코드 : %s" % subject_code)
                    if subject_symbol in self.subject_var.info:
                        self.log.debug("금일 %s의 종목코드는 %s 입니다." % (self.subject_var.info[subject_symbol]["종목명"], subject_code))
                        self.subject_var.info[subject_code] = self.subject_var.info[subject_symbol]
                        self.strategy_var.info[subject_code] = self.strategy_var.info[subject_symbol]
                        del self.subject_var.info[subject_symbol]
                        del self.strategy_var.info[subject_symbol]

                        self.chart_manager.init_data(subject_code)
                        # 초기 데이터 요청
                        for chart_config in self.strategy_var.info[subject_code][self.subject_var.info[subject_code]['전략']][const.차트]:
                            type_ = chart_config[0]
                            time_unit = chart_config[1]

                            self.log.debug("chart_config : %s" % chart_config)
                            if type_ == const.틱차트:
                                self.request_tick_info(subject_code, time_unit, "")
                            elif type_ == const.분차트:
                                self.request_min_info(subject_code, time_unit, "")

            elif '해외선물옵션틱차트조회' in sRQName:
                params = sRQName.split('_')
                chart_type = const.틱차트
                time_unit = params[2]
                subject_code = params[1]

                self.log.debug("해외선물옵션틱차트조회 params : %s" % params)

                if subject_code in self.subject_var.info:
                    if const.MODE is const.REAL:
                        data_str = self.ocx.dynamicCall("GetCommFullData(QString, QString, int)", sTrCode,
                                                        sRecordName, 0)

                        chart_data = self.chart_manager.data[subject_code][chart_type][time_unit]  # 차트 타입과 시간단위에 맞는 차트 불러옴

                        if len(chart_data['임시데이터']) == 0:
                            ''' 가장 처음 데이터가 수신 되었을 때 '''
                            self.log.debug("데이터 수신 시작. 차트구분 : %s, 시간단위 : %s" % (chart_type, time_unit))
                            chart_data['임시데이터'] = data_str.split()

                            chart_data['현재가변동횟수'] = int(chart_data['임시데이터'][0])
                            chart_data['현재캔들'] = {}
                            chart_data['현재캔들'][const.현재가] = float(chart_data['임시데이터'][1])
                            chart_data['현재캔들']['거래량'] = int(chart_data['임시데이터'][2])
                            chart_data['현재캔들'][const.체결시간] = str(chart_data['임시데이터'][3])
                            chart_data['현재캔들'][const.시가] = float(chart_data['임시데이터'][4])
                            chart_data['현재캔들'][const.고가] = float(chart_data['임시데이터'][5])
                            chart_data['현재캔들'][const.저가] = float(chart_data['임시데이터'][6])
                            chart_data['현재캔들']['영업일자'] = str(chart_data['임시데이터'][7])

                            chart_data['임시캔들'] = []    # 초기 데이터 수신 중 완성된 캔들을 임시로 저장하고, 수신이 완료된 후 Push

                            if chart_data['현재가변동횟수'] == int(time_unit):
                                self.log.debug("수신 된 첫 캔들이 이미 완성된 캔들이므로, 임시 캔들에 추가함.")
                                chart_data['임시캔들'].append(chart_data['현재캔들'])
                                self.chart_manager.init_current_candle(subject_code, chart_type, time_unit)

                            for tick in chart_data['임시틱']:
                                ''' 첫 번째 데이터 수신 전 해당 차트로부터 들어온 Tick들 처리 '''
                                if chart_data['현재가변동횟수'] == 0:
                                    chart_data['현재캔들'][const.시가] = tick[0]

                                chart_data['현재가변동횟수'] += 1
                                if tick[0] < chart_data['현재캔들'][const.저가]:
                                    chart_data['현재캔들'][const.저가] = tick[0]
                                if tick[0] > chart_data['현재캔들'][const.고가]:
                                    chart_data['현재캔들'][const.고가] = tick[0]

                                if chart_data['현재가변동횟수'] == time_unit:
                                    chart_data['현재캔들'][const.체결시간] = tick[1]
                                    chart_data['현재캔들'][const.현재가] = tick[0]
                                    chart_data['현재가변동횟수'] = 0
                                    if chart_data['인덱스'] == -1:
                                        chart_data['임시캔들'].append(chart_data['현재캔들'])
                                    else:
                                        self.chart_manager.push(subject_code, chart_type, time_unit, chart_data['현재캔들'])
                        else:
                            ''' 데이터 수신 중간 '''
                            self.log.debug("데이터 수신 중. 차트구분 : %s, 시간단위 : %s" % (chart_type, time_unit))
                            chart_data['임시데이터'] = chart_data['임시데이터'] + data_str.split()[1:]

                        if len(chart_data['임시데이터']) / 7 > self.strategy_var.info[subject_code][self.subject_var.info[subject_code]['전략']][const.차트변수][chart_type][time_unit][const.초기캔들수]:
                            ''' 데이터 수신 완료 '''

                            self.log.debug("데이터 수신 완료. 차트구분 : %s, 시간단위 : %s" % (chart_type, time_unit))
                            current_idx = len(chart_data['임시데이터']) - 7

                            candle = {}
                            while current_idx > 8:
                                candle[const.현재가] = float(chart_data['임시데이터'][current_idx])
                                candle['거래량'] = int(chart_data['임시데이터'][current_idx + 1])
                                candle[const.체결시간] = str(chart_data['임시데이터'][current_idx + 2])
                                candle[const.시가] = float(chart_data['임시데이터'][current_idx + 3])
                                candle[const.고가] = float(chart_data['임시데이터'][current_idx + 4])
                                candle[const.저가] = float(chart_data['임시데이터'][current_idx + 5])
                                candle['영업일자'] = str(chart_data['임시데이터'][current_idx + 6])
                                current_idx -= 7

                                self.chart_manager.push(subject_code, chart_type, time_unit, candle)

                            if len(chart_data['임시캔들']) > 0:
                                self.log.debug("데이터 수신 중 완성된 임시캔들들 Push.")
                                for candle in chart_data['임시캔들']:
                                    self.chart_manager.push(subject_code, chart_type, time_unit, candle)

                            isEnd = True
                            for chart_config in self.strategy_var.info[subject_code][self.subject_var.info[subject_code]['전략']][const.차트]:
                                chart_type = chart_config[0]
                                time_unit = chart_config[1]

                                if self.chart_manager.data[subject_code][chart_type][time_unit]['인덱스'] < \
                                        self.strategy_var.info[subject_code][self.subject_var.info[subject_code]['전략']][const.차트변수][chart_type][time_unit][const.초기캔들수]:
                                    isEnd = False
                                    break

                            if isEnd:
                                self.chart_manager.data[subject_code]['상태'] = '매매가능'

                        else:
                            self.request_tick_info(subject_code, time_unit, sPreNext)

                    elif const.MODE is const.TEST:
                        pass

            elif sRQName == '미결제잔고내역조회':
                order_info = {}
                contract_cnt = int(
                    self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRecordName, 1,
                                         '매도수량'))

                if contract_cnt is 0:
                    contract_cnt = int(
                        self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRecordName, 1,
                                             '매수수량'))
                    order_info['매도수구분'] = const.매수
                else:
                    order_info['매도수구분'] = const.매도

                if contract_cnt is 0:
                    return

                order_info['종목코드'] = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                          sRecordName, 0, '종목코드').strip()
                order_info['신규수량'] = contract_cnt
                order_info['체결표시가격'] = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                            sRecordName, 0, '평균단가').strip()
                self.log.debug("미결제잔고내역조회 : %s", order_info)

                '''
                if self.state == '매매가능': return
                self.state = '매매가능'
                order_info = {}
                order_contents = {}
                contract_cnt = int(
                    self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRecordName, 1,
                                         '매도수량'))

                if contract_cnt is 0:
                    contract_cnt = int(
                        self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRecordName, 1,
                                             '매수수량'))
                    order_contents['매도수구분'] = '신규매수'
                else:
                    order_contents['매도수구분'] = '신규매도'

                if contract_cnt is 0: return

                order_info['종목코드'] = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                          sRecordName, 0, '종목코드').strip()
                order_info['신규수량'] = contract_cnt
                order_info['체결표시가격'] = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                                                            sRecordName, 0, '평균단가').strip()
                order_contents['익절틱'] = self.subject_var.info[order_info['종목코드']]['익절틱']
                order_contents['손절틱'] = self.subject_var.info[order_info['종목코드']]['손절틱']

                contract.add_contract(order_info, order_contents)
                '''

            elif sRQName == "예수금및증거금현황조회":
                self.account_pwd_input = True
                self.contract_manager.예수금 = int(
                    self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRecordName, 0,
                                         '주문가능금액').strip())
                self.log.debug('예수금 현황 : ' + str(self.contract_manager.예수금))

        except Exception as err:
            self.log.error(util.get_error_msg(err))

    def OnReceiveChejanData(self, sGubun, nItemCnt, sFidList, o_info=None):
        """
        체결데이터를 받은 시점을 알려준다.

        :type o_info: object
        :param sGubun: 체결구분 - 0:주문체결통보, 1:잔고통보, 3:특이신호
        :param nItemCnt: 아이템갯수
        :param sFidList: 데이터리스트 - 데이터 구분은 ‘;’ 이다.
        """
        self.log.debug("onReceiveChejanData (%s, %s, %s)" % (sGubun, nItemCnt, sFidList))

        try:
            if sGubun == '1':
                order_info = {}

                if const.MODE == const.REAL:  # 실제투자
                    order_info['주문번호'] = int(self.ocx.dynamicCall("GetChejanData(int)", 9203))  # 주문번호
                    order_info['원주문번호'] = int(self.ocx.dynamicCall("GetChejanData(int)", 904))  # 원주문번호
                    order_info['주문유형'] = int(
                        self.ocx.dynamicCall("GetChejanData(int)", 906))  # 주문유형(1 : 시장가, 2 : 지정가, 3 : STOP)
                    order_info['종목코드'] = self.ocx.dynamicCall("GetChejanData(int)", 9001)  # 종목코드
                    order_info['매도수구분'] = int(self.ocx.dynamicCall("GetChejanData(int)", 907))  # 매도수구분(1 : 매도, 2 : 매수)
                    order_info['체결표시가격'] = self.ocx.dynamicCall("GetChejanData(int)", 13331)  # 체결표시가격
                    order_info['신규수량'] = self.ocx.dynamicCall("GetChejanData(int)", 13327)  # 신규수량
                    order_info['청산수량'] = self.ocx.dynamicCall("GetChejanData(int)", 13328)  # 청산수량
                    order_info['체결수량'] = self.ocx.dynamicCall("GetChejanData(int)", 911)  # 체결수량

                    self.get_my_deposit_info()
                elif const.MODE == const.TEST:  # 테스트
                    order_info = o_info

                order_info['체결표시가격'] = round(float(order_info['체결표시가격']), self.subject_var.info[order_info['종목코드']]['자릿수'])

                add_cnt = int(order_info['신규수량'])
                remove_cnt = int(order_info['청산수량'])

                ''' 청산 체결 '''
                if remove_cnt > 0:
                    msg = '청산주문 체결 [%s]' % order_info
                    self.res.info(msg)
                    수익 = self.contract_manager.remove_contract(order_info)
                    self.누적수익 += 수익

                    self.telepot.send_message('%s, 체결수익 : %s, 누적수익 : %s' % (msg, 수익, self.누적수익))

                ''' 신규 매매 체결 '''
                if add_cnt > 0:
                    msg = '신규주문 체결 [%s]' % order_info
                    self.res.info('신규주문 체결 [%s]' % order_info)
                    self.contract_manager.add_contract(order_info)
                    self.telepot.send_message(msg)

        except Exception as err:
            self.log.error(util.get_error_msg(err))

    def OnReceiveRealData(self, subject_code, sRealType, sRealData):
        """
        실시간 시세 이벤트
        실시간데이터를 받은 시점을 알려준다.

        :param subject_code: 종목코드
        :param sRealType: 리얼타입
        :param sRealData: 실시간 데이터전문
        """

        try:
            if subject_code not in self.subject_var.info:
                # log.error("요청하지 않은 데이터 수신. (%s, %s, %s)" % (subject_code, sRealType, sRealData))
                return

            # res.info("RealData (%s, %s, %s)" % (subject_code, sRealType, sRealData))

            current_price = None
            current_time = None

            if const.MODE == const.REAL:
                current_price = self.ocx.dynamicCall("GetCommRealData(QString, int)", "현재가", 140)  # 140은 현재가의 코드
                current_time = self.ocx.dynamicCall("GetCommRealData(QString, int)", "체결시간", 20)  # 20은 체결시간의 코드
            elif const.MODE == const.TEST:
                current_price = sRealType
                current_time = sRealData

            current_price = round(float(current_price), self.subject_var.info[subject_code]['자릿수'])

            if const.MODE == const.REAL:
                ''' Send Request '''
                now = time.time()
                if now - self.last_req_time > 0.25:
                    self.send_request()
                    self.last_req_time = now

                ''' 계좌번호 비밀번호 입력했는지 체크 '''
                if now-self.last_pwd_check_time > 2 and self.account_pwd_input is False:
                    self.get_my_deposit_info()
                    self.get_contract_list()
                    self.last_pwd_check_time = now

            chart_data = None

            ''' 캔들 생성 '''
            for chart_config in self.strategy_var.info[subject_code][self.subject_var.info[subject_code]['전략']][const.차트]:
                chart_type = chart_config[0]
                time_unit = chart_config[1]

                chart_data = self.chart_manager.data[subject_code][chart_type][time_unit]
                if chart_type == const.틱차트:
                    if len(chart_data['현재캔들'].keys()) is 0:
                        chart_data['임시틱'].append([current_price, current_time])
                        return

                    if chart_data['현재가변동횟수'] == 0:
                        chart_data['현재캔들'][const.시가] = current_price

                    chart_data['현재가변동횟수'] += 1
                    if current_price < chart_data['현재캔들'][const.저가]:
                        chart_data['현재캔들'][const.저가] = current_price

                    if current_price > chart_data['현재캔들'][const.고가]:
                        chart_data['현재캔들'][const.고가] = current_price

                    if chart_data['현재가변동횟수'] == int(time_unit):
                        chart_data['현재캔들'][const.체결시간] = current_time
                        chart_data['현재캔들'][const.현재가] = current_price
                        chart_data['현재가변동횟수'] = 0
                        if chart_data['인덱스'] == -1 and const.MODE == const.REAL:
                            chart_data['임시캔들'].append(chart_data['현재캔들'])
                        else:
                            # log.info('%s, %s, %s, %s' % (subject_code, chart_type, time_unit, chart_data['현재캔들']))
                            self.chart_manager.push(subject_code, chart_type, time_unit, chart_data['현재캔들'])

                        self.chart_manager.init_current_candle(subject_code, chart_type, time_unit)

                elif chart_type == const.분차트:
                    pass

            # 현재 Event의 전략을 나타내는 변수
            # Strategy manager를 통해서 전략을 받아와야 한다.
            current_strategy = self.strategy_manager.get_strategy(subject_code)

            ''' 계약 청산 '''
            if self.contract_manager.get_contract_count(subject_code) > 0:
                sell_contents = current_strategy.is_it_sell(subject_code, current_price)

                if sell_contents['신규주문']:
                    self.send_order(sell_contents['매도수구분'], subject_code, sell_contents['수량'])

            ''' 매매 진입 '''
            if self.contract_manager.get_contract_count(subject_code) == 0:
                order_contents = current_strategy.is_it_ok(subject_code, current_price)

                if order_contents['신규주문']:
                    self.res.info('신규주문 : %s' % order_contents)
                    self.res.info("체결시간:%s" % chart_data[const.체결시간][-1])
                    self.send_order(order_contents['매도수구분'], subject_code, order_contents['수량'])

            ''' 전략 선택 '''
            self.strategy_manager.strategy_selector(subject_code)

        except Exception:
            pass
            # self.log.error(get_error_msg(err))

    ####################################################
    # Test Function
    ####################################################

    def receiveTestData(self, candle):
        # chart_manager 계산
        # 매매
        pass

    def get_name(self):
        return str(self.__class__.__name__)

    def print_status(self):
        print(self.__getattribute__())