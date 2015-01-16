import os

from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr
from migen.bus import wishbone2csr
from migen.genlib.cdc import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bank.description import *

from miscope import MiLa, Term, UART2Wishbone

from misoclib import identifier
from lib.sata.common import *
from lib.sata.phy import SATAPHY
from lib.sata import SATACON
from lib.sata.bist import SATABIST, SATABISTControl

class _CRG(Module):
	def __init__(self, platform):
		self.cd_sys = ClockDomain()
		self.sata_reset = Signal()

		clk200 = platform.request("clk200")
		clk200_se = Signal()
		self.specials += Instance("IBUFDS", i_I=clk200.p, i_IB=clk200.n, o_O=clk200_se)

		pll_locked = Signal()
		pll_fb = Signal()
		pll_sys = Signal()
		self.specials += [
			Instance("PLLE2_BASE",
				p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

				# VCO @ 1GHz
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=5.0,
				p_CLKFBOUT_MULT=5, p_DIVCLK_DIVIDE=1,
				i_CLKIN1=clk200_se, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

				# 166MHz
				p_CLKOUT0_DIVIDE=6, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, #o_CLKOUT1=,

				p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.0, #o_CLKOUT2=,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=2, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked | platform.request("cpu_reset") | self.sata_reset),
		]

class GenSoC(Module):
	csr_base = 0x00000000
	csr_data_width = 32
	csr_map = {
		"uart2wb":			0,
		"identifier":		2,
	}
	interrupt_map = {}
	cpu_type = None
	def __init__(self, platform, clk_freq):
		# UART <--> Wishbone bridge
		self.uart2wb = UART2Wishbone(platform.request("serial"), clk_freq, baud=921600)

		# CSR bridge   0x00000000 (shadow @0x00000000)
		self.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(self.csr_data_width))
		self._wb_masters = [self.uart2wb.wishbone]
		self._wb_slaves = [(lambda a: a[23:25] == 0, self.wishbone2csr.wishbone)]
		self.cpu_csr_regions = [] # list of (name, origin, busword, csr_list/Memory)

		# CSR
		self.identifier = identifier.Identifier(0, int(clk_freq), 0)

	def add_cpu_memory_region(self, name, origin, length):
		self.cpu_memory_regions.append((name, origin, length))

	def add_cpu_csr_region(self, name, origin, busword, obj):
		self.cpu_csr_regions.append((name, origin, busword, obj))

	def do_finalize(self):
		# Wishbone
		self.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		self.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override],
			data_width=self.csr_data_width)
		self.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())
		for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
			self.add_cpu_csr_region(name, 0xe0000000+0x800*mapaddr, flen(rmap.bus.dat_w), csrs)
		for name, memory, mapaddr, mmap in self.csrbankarray.srams:
			self.add_cpu_csr_region(name, 0xe0000000+0x800*mapaddr, flen(rmap.bus.dat_w), memory)

class BISTLeds(Module):
	def __init__(self, platform, sata_phy):
		# 1Hz blinking leds (sata_rx and sata_tx clocks)
		sata_rx_led = platform.request("user_led", 0)
		sata_tx_led = platform.request("user_led", 1)

		sata_rx_cnt = Signal(32)
		sata_tx_cnt = Signal(32)

		sata_freqs_mhz = {
			"SATA3"	:	150.0,
			"SATA2"	:	75.0,
			"SATA1"	:	37.5,
		}
		sata_freq = int(sata_freqs_mhz[sata_phy.speed]*1000*1000)

		self.sync.sata_rx += \
			If(sata_rx_cnt == 0,
				sata_rx_led.eq(~sata_rx_led),
				sata_rx_cnt.eq(sata_freq//2)
			).Else(
				sata_rx_cnt.eq(sata_rx_cnt-1)
			)

		self.sync.sata_tx += \
			If(sata_tx_cnt == 0,
				sata_tx_led.eq(~sata_tx_led),
				sata_tx_cnt.eq(sata_freq//2)
			).Else(
				sata_tx_cnt.eq(sata_tx_cnt-1)
			)

		# ready leds (crg and ctrl)
		self.comb += platform.request("user_led", 2).eq(sata_phy.crg.ready)
		self.comb += platform.request("user_led", 3).eq(sata_phy.ctrl.ready)

class BISTSoC(GenSoC, AutoCSR):
	default_platform = "kc705"
	csr_map = {
		"sata_bist":	10,
	}
	csr_map.update(GenSoC.csr_map)

	def __init__(self, platform, export_mila=False):
		clk_freq = 166*1000000
		GenSoC.__init__(self, platform, clk_freq)
		self.crg = _CRG(platform)

		# SATA PHY and controller
		self.sata_phy = SATAPHY(platform.request("sata_host"), clk_freq, speed="SATA2")
		self.comb += self.crg.sata_reset.eq(self.sata_phy.ctrl.need_reset)
		self.sata_con = SATACON(self.sata_phy)

		# SATA BIST generator and checker
		self.sata_bist = SATABIST(self.sata_con.crossbar.get_ports(2), with_control=True)

		# Status Leds
		self.leds = BISTLeds(platform, self.sata_phy)

class BISTSoCDevel(BISTSoC, AutoCSR):
	csr_map = {
		"mila":			11
	}
	csr_map.update(BISTSoC.csr_map)
	def __init__(self, platform, export_mila=False):
		BISTSoC.__init__(self, platform, export_mila)

		debug = (
			self.sata_phy.ctrl.ready,

			self.sata_phy.source.stb,
			self.sata_phy.source.data,
			self.sata_phy.source.charisk,

			self.sata_phy.sink.stb,
			self.sata_phy.sink.data,
			self.sata_phy.sink.charisk,

			self.sata_con.command.sink.stb,
			self.sata_con.command.sink.sop,
			self.sata_con.command.sink.eop,
			self.sata_con.command.sink.ack,
			self.sata_con.command.sink.write,
			self.sata_con.command.sink.read,

			self.sata_con.command.source.stb,
			self.sata_con.command.source.sop,
			self.sata_con.command.source.eop,
			self.sata_con.command.source.ack,
			self.sata_con.command.source.write,
			self.sata_con.command.source.read,
			self.sata_con.command.source.success,
			self.sata_con.command.source.failed,
			self.sata_con.command.source.data
		)

		self.mila = MiLa(depth=2048, dat=Cat(*debug))
		self.mila.add_port(Term)
		if export_mila:
			mila_filename = os.path.join(platform.soc_ext_path, "test", "mila.csv")
			self.mila.export(self, debug, mila_filename)

#default_subtarget = BISTSoC
default_subtarget = BISTSoCDevel
