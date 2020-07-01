#
#   Copyright 2019 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import time

from bluetooth_packets_python3 import hci_packets
from cert.event_stream import EventStream
from cert.gd_base_test import GdBaseTestClass
from cert.matchers import HciMatchers
from cert.metadata import metadata
from cert.py_hci import PyHci
from cert.py_le_security import PyLeSecurity
from cert.truth import assertThat
from datetime import timedelta
from facade import common_pb2 as common
from hci.facade import controller_facade_pb2 as controller_facade
from hci.facade import le_advertising_manager_facade_pb2 as le_advertising_facade
from hci.facade import le_initiator_address_facade_pb2 as le_initiator_address_facade
from google.protobuf import empty_pb2 as empty_proto
from neighbor.facade import facade_pb2 as neighbor_facade
from security.cert.cert_security import CertSecurity
from security.facade_pb2 import AuthenticationRequirements
from security.facade_pb2 import BondMsgType
from security.facade_pb2 import OobDataPresent
from security.facade_pb2 import OobDataMessage
from security.facade_pb2 import UiCallbackMsg
from security.facade_pb2 import UiCallbackType
from security.facade_pb2 import UiMsgType
from security.facade_pb2 import LeAuthReqMsg
from security.facade_pb2 import LeIoCapabilityMessage
from bluetooth_packets_python3.hci_packets import OpCode


class LeSecurityTest(GdBaseTestClass):
    """
        Collection of tests that each sample results from
        different (unique) combinations of io capabilities, authentication requirements, and oob data.
    """

    def setup_class(self):
        super().setup_class(dut_module='SECURITY', cert_module='SECURITY')

    def setup_test(self):
        super().setup_test()

        self.dut_security = PyLeSecurity(self.dut)
        self.cert_security = PyLeSecurity(self.cert)
        self.dut_hci = PyHci(self.dut)

        self.dut_address = common.BluetoothAddressWithType(
            address=common.BluetoothAddress(address=bytes(b'DD:05:04:03:02:01')), type=common.RANDOM_DEVICE_ADDRESS)
        privacy_policy = le_initiator_address_facade.PrivacyPolicy(
            address_policy=le_initiator_address_facade.AddressPolicy.USE_STATIC_ADDRESS,
            address_with_type=self.dut_address)
        self.dut.security.SetLeInitiatorAddressPolicy(privacy_policy)
        self.cert_address = common.BluetoothAddressWithType(
            address=common.BluetoothAddress(address=bytes(b'C5:11:FF:AA:33:22')), type=common.RANDOM_DEVICE_ADDRESS)
        cert_privacy_policy = le_initiator_address_facade.PrivacyPolicy(
            address_policy=le_initiator_address_facade.AddressPolicy.USE_STATIC_ADDRESS,
            address_with_type=self.cert_address)
        self.cert.security.SetLeInitiatorAddressPolicy(cert_privacy_policy)

    def teardown_test(self):
        self.dut_hci.close()
        self.dut_security.close()
        self.cert_security.close()
        super().teardown_test()

    def _prepare_cert_for_connection(self):
        # DUT Advertises
        gap_name = hci_packets.GapData()
        gap_name.data_type = hci_packets.GapDataType.COMPLETE_LOCAL_NAME
        gap_name.data = list(bytes(b'Im_The_CERT'))
        gap_data = le_advertising_facade.GapDataMsg(data=bytes(gap_name.Serialize()))
        config = le_advertising_facade.AdvertisingConfig(
            advertisement=[gap_data],
            interval_min=512,
            interval_max=768,
            event_type=le_advertising_facade.AdvertisingEventType.ADV_IND,
            address_type=common.RANDOM_DEVICE_ADDRESS,
            channel_map=7,
            filter_policy=le_advertising_facade.AdvertisingFilterPolicy.ALL_DEVICES)
        request = le_advertising_facade.CreateAdvertiserRequest(config=config)
        create_response = self.cert.hci_le_advertising_manager.CreateAdvertiser(request)

    def _prepare_dut_for_connection(self):
        # DUT Advertises
        gap_name = hci_packets.GapData()
        gap_name.data_type = hci_packets.GapDataType.COMPLETE_LOCAL_NAME
        gap_name.data = list(bytes(b'Im_The_DUT'))
        gap_data = le_advertising_facade.GapDataMsg(data=bytes(gap_name.Serialize()))
        config = le_advertising_facade.AdvertisingConfig(
            advertisement=[gap_data],
            interval_min=512,
            interval_max=768,
            event_type=le_advertising_facade.AdvertisingEventType.ADV_IND,
            address_type=common.RANDOM_DEVICE_ADDRESS,
            channel_map=7,
            filter_policy=le_advertising_facade.AdvertisingFilterPolicy.ALL_DEVICES)
        request = le_advertising_facade.CreateAdvertiserRequest(config=config)
        create_response = self.dut.hci_le_advertising_manager.CreateAdvertiser(request)

    @metadata(pts_test_id="SM/MAS/PROT/BV-01-C", pts_test_name="SMP Time Out – IUT Initiator")
    def test_le_smp_timeout_iut_initiator(self):
        """
            Verify that the IUT handles the lack of pairing response after 30 seconds when acting as initiator.
        """
        self._prepare_cert_for_connection()
        self.dut.security.CreateBondLe(self.cert_address)
        self.dut_security.wait_for_bond_event(
            expected_bond_event=BondMsgType.DEVICE_BOND_FAILED, timeout=timedelta(seconds=35))

    @metadata(pts_test_id="SM/SLA/PROT/BV-02-C", pts_test_name="SMP Time Out – IUT Responder")
    def test_le_smp_timeout_iut_responder(self):
        """
            Verify that the IUT handles the lack of pairing response after 30 seconds when acting as initiator.
        """
        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_ONLY))
        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.DISPLAY_ONLY))

        self._prepare_dut_for_connection()

        # 1. Lower Tester transmits Pairing Request.
        self.cert.security.CreateBondLe(self.dut_address)

        self.dut_security.wait_for_ui_event(
            expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT, timeout=timedelta(seconds=35))

        # 2. IUT responds with Pairing Response.
        self.dut.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.cert_address))

        # 3. In phase 2, Lower Tester does not issue the expected Pairing Confirm.

        # Here the cert receives DISPLAY_PASSKEY_ENTRY. By not replying to it we make sure Pairing Confirm is never sent
        self.cert_security.wait_for_ui_event(
            expected_ui_event=UiMsgType.DISPLAY_PASSKEY_ENTRY, timeout=timedelta(seconds=5))

        # 4. IUT times out 30 seconds after issued Pairing Response and reports the failure to the Upper Tester.
        self.dut_security.wait_for_bond_event(
            expected_bond_event=BondMsgType.DEVICE_BOND_FAILED, timeout=timedelta(seconds=35))

        # 5. After additionally (at least) 10 seconds the Lower Tester issues the expected Pairing Confirm.
        # 6. The IUT closes the connection before receiving the delayed response or does not respond to it when it is received.
        #TODO:
        #assertThat(self.dut_hci.get_event_stream()).emits(HciMatchers.Disconnect())

    @metadata(pts_test_id="SM/MAS/JW/BV-01-C", pts_test_name="Just Works IUT Initiator – Success")
    def test_just_works_iut_initiator(self):
        """
            Verify that the IUT performs the Just Works pairing procedure correctly as master, initiator when both sides do not require MITM protection.
        """
        self._prepare_cert_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_ONLY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x00))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.DISPLAY_ONLY))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x00))

        # 1. IUT transmits Pairing Request command with:
        # a. IO capability set to any IO capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq Bonding Flags set to ‘00’ and the MITM flag set to ‘0’ and all the reserved bits are set to ‘0’
        self.dut.security.CreateBondLe(self.cert_address)

        self.cert_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. Lower Tester responds with a Pairing Response command, with:
        # a. IO capability set to “KeyboardDisplay”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq Bonding Flags set to ‘00’, and the MITM flag set to ‘0’ and all the reserved bits are set to ‘0’
        self.cert.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.cert_address))

        # 3. IUT and Lower Tester perform phase 2 of the just works pairing procedure and establish an encrypted link with the key generated in phase 2.
        self.dut_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(pts_test_id="SM/SLA/JW/BV-02-C", pts_test_name="Just Works IUT Responder – Success")
    def test_just_works_iut_responder(self):
        """
            Verify that the IUT is able to perform the Just Works pairing procedure correctly when acting as slave, responder.
        """
        self._prepare_dut_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_ONLY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x00))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.NO_INPUT_NO_OUTPUT))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x00))

        # 1. Lower Tester transmits Pairing Request command with:
        # a. IO capability set to “NoInputNoOutput”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. MITM flag set to ‘0’ and all reserved bits are set to ‘0’
        self.cert.security.CreateBondLe(self.dut_address)

        self.dut_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. IUT responds with a Pairing Response command, with:
        # a. IO capability set to any IO capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        self.dut.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.dut_address))

        # IUT and Lower Tester perform phase 2 of the just works pairing and establish an encrypted link with the generated STK.
        self.dut_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(
        pts_test_id="SM/SLA/JW/BI-03-C", pts_test_name="Just Works IUT Responder – Handle AuthReq flag RFU correctly")
    def test_just_works_iut_responder_auth_req_rfu(self):
        """
            Verify that the IUT is able to perform the Just Works pairing procedure when receiving additional bits set in the AuthReq flag. Reserved For Future Use bits are correctly handled when acting as slave, responder.
        """
        self._prepare_dut_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_DISPLAY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x00))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.NO_INPUT_NO_OUTPUT))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x0C))

        # 1. Lower Tester transmits Pairing Request command with:
        # a. IO Capability set to ”NoInputNoOutput”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. MITM set to ‘0’ and all reserved bits are set to ‘1’
        self.cert.security.CreateBondLe(self.dut_address)

        self.dut_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. IUT responds with a Pairing Response command, with:
        # a. IO capability set to any IO capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. All reserved bits are set to ‘0’
        self.dut.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.dut_address))

        # 3. IUT and Lower Tester perform phase 2 of the just works pairing and establish an encrypted link with the generated STK.
        self.dut_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(
        pts_test_id="SM/MAS/JW/BI-04-C", pts_test_name="Just Works IUT Initiator – Handle AuthReq flag RFU correctly")
    def test_just_works_iut_initiator_auth_req_rfu(self):
        """
            Verify that the IUT is able to perform the Just Works pairing procedure when receiving additional bits set in the AuthReq flag. Reserved For Future Use bits are correctly handled when acting as master, initiator.
        """
        self._prepare_cert_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_DISPLAY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x00))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.NO_INPUT_NO_OUTPUT))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x0C))

        # 1. IUT transmits a Pairing Request command with:
        # a. IO Capability set to any IO Capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. All reserved bits are set to ‘0’. For the purposes of this test the Secure Connections bit and the Keypress bits in the AuthReq bonding flag set by the IUT are ignored by the Lower Tester.
        self.dut.security.CreateBondLe(self.cert_address)

        self.cert_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. Lower Tester responds with a Pairing Response command, with:
        # a. IO Capability set to “NoInputNoOutput”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq bonding flag set to the value indicated in the IXIT [7] for ‘Bonding Flags’ and the MITM flag set to ‘0’ and all reserved bits are set to ‘1’. The SC and Keypress bits in the AuthReq bonding flag are set to 0 by the Lower Tester for this test.
        self.cert.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.cert_address))

        # 3. IUT and Lower Tester perform phase 2 of the just works pairing and establish an encrypted link with the generated STK.
        self.cert_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(
        pts_test_id="SM/MAS/SCJW/BV-01-C", pts_test_name="Just Works, IUT Initiator, Secure Connections – Success")
    def test_just_works_iut_initiator_secure_connections(self):
        """
            Verify that the IUT supporting LE Secure Connections performs the Just Works or Numeric Comparison pairing procedure correctly as initiator.
        """
        self._prepare_cert_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_ONLY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x08))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.DISPLAY_ONLY))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x08))

        # 1. IUT transmits Pairing Request command with:
        # a. IO capability set to any IO capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq Bonding Flags set to ‘00’, the MITM flag set to either ‘0’ for Just Works or '1' for Numeric Comparison, Secure Connections flag set to '1' and all the reserved bits are set to ‘0’
        self.dut.security.CreateBondLe(self.cert_address)

        self.cert_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. Lower Tester responds with a Pairing Response command, with:
        # a. IO capability set to “KeyboardDisplay”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq Bonding Flags set to ‘00’, the MITM flag set to ‘0’, Secure Connections flag set to '1' and all the reserved bits are set to ‘0’
        self.cert.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.cert_address))

        # 3. IUT and Lower Tester perform phase 2 of the Just Works or Numeric Comparison pairing procedure according to the MITM flag and IO capabilities, and establish an encrypted link with the LTK generated in phase 2.
        self.dut_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(
        pts_test_id="SM/SLA/SCJW/BV-02-C", pts_test_name="Just Works, IUT Responder, Secure Connections – Success")
    def test_just_works_iut_responder_secure_connections(self):
        """
            Verify that the IUT supporting LE Secure Connections is able to perform the Just Works or Numeric Comparison pairing procedure correctly when acting as responder.
        """
        self._prepare_dut_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_ONLY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x08))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.NO_INPUT_NO_OUTPUT))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x08))

        # 1. Lower Tester transmits Pairing Request command with:
        # a. IO capability set to “NoInputNoOutput”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq Bonding Flags set to ‘00’, MITM flag set to ‘0’, Secure Connections flag set to '1' and all reserved bits are set to ‘0’
        self.cert.security.CreateBondLe(self.dut_address)

        self.dut_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. IUT responds with a Pairing Response command, with:
        # a. IO capability set to any IO capability
        # b. AuthReq Bonding Flags set to ‘00’, MITM flag set to either ‘0’ for Just Works or '1' for Numeric Comparison, Secure Connections flag set to '1' and all reserved bits are set to ‘0’
        self.dut.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.dut_address))

        # 3. UT and Lower Tester perform phase 2 of the Just Works or Numeric Comparison pairing procedure according to the MITM flag and IO capabilities, and establish an encrypted link with the LTK generated in phase 2.
        self.dut_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(
        pts_test_id="SM/SLA/SCJW/BV-03-C",
        pts_test_name="Just Works, IUT Responder, Secure Connections – Handle AuthReq Flag RFU Correctly")
    def test_just_works_iut_responder_secure_connections_auth_req_rfu(self):
        """
            Verify that the IUT is able to perform the Just Works pairing procedure when receiving additional bits set in the AuthReq flag. Reserved For Future Use bits are correctly handled when acting as slave, responder.
        """
        self._prepare_dut_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_DISPLAY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x08))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.NO_INPUT_NO_OUTPUT))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x0C))

        # 1. Lower Tester transmits Pairing Request command with:
        # a. IO Capability set to ”NoInputNoOutput”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. MITM set to ‘0’ and all reserved bits are set to a random value.
        self.cert.security.CreateBondLe(self.dut_address)

        self.dut_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. IUT responds with a Pairing Response command, with:
        # a. IO capability set to any IO capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. All reserved bits are set to ‘0’
        self.dut.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.dut_address))

        # 3. IUT and Lower Tester perform phase 2 of the Just Works pairing and establish an encrypted link with the generated LTK.
        self.dut_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)

    @metadata(
        pts_test_id="SM/MAS/SCJW/BV-04-C",
        pts_test_name="Just Works, IUT Initiator, Secure Connections – Handle AuthReq Flag RFU Correctly")
    def test_just_works_iut_initiator_secure_connections_auth_req_rfu(self):
        """
            Verify that the IUT is able to perform the Just Works pairing procedure when receiving additional bits set in the AuthReq flag. Reserved For Future Use bits are correctly handled when acting as master, initiator.
        """
        self._prepare_cert_for_connection()

        self.dut.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.KEYBOARD_DISPLAY))
        self.dut.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.dut.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x08))

        self.cert.security.SetLeIoCapability(
            LeIoCapabilityMessage(capabilities=LeIoCapabilityMessage.LeIoCapabilities.NO_INPUT_NO_OUTPUT))
        self.cert.security.SetOobDataPresent(OobDataMessage(data_present=OobDataPresent.NOT_PRESENT))
        self.cert.security.SetLeAuthReq(LeAuthReqMsg(auth_req=0x0C))

        # 1. IUT transmits a Pairing Request command with:
        # a. IO Capability set to any IO Capability
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. All reserved bits are set to ‘0’.
        self.dut.security.CreateBondLe(self.cert_address)

        self.cert_security.wait_for_ui_event(expected_ui_event=UiMsgType.DISPLAY_PAIRING_PROMPT)

        # 2. Lower Tester responds with a Pairing Response command, with:
        # a. IO Capability set to “NoInputNoOutput”
        # b. OOB data flag set to 0x00 (OOB Authentication data not present)
        # c. AuthReq bonding flag set to the value indicated in the IXIT [7] for ‘Bonding Flags’ and the MITM flag set to ‘0’ and all reserved bits are set to a random value.
        self.cert.security.SendUiCallback(
            UiCallbackMsg(
                message_type=UiCallbackType.PAIRING_PROMPT, boolean=True, unique_id=1, address=self.cert_address))

        # 3. IUT and Lower Tester perform phase 2 of the Just Works pairing and establish an encrypted link with the generated LTK.
        self.cert_security.wait_for_bond_event(expected_bond_event=BondMsgType.DEVICE_BONDED)