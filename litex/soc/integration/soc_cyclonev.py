# This file is Copyright (c) 2020 Ignacio Lesser <ignacio.lesser@gmail.com>
# License: BSD

import os

from migen import Signal, ResetSignal, ClockSignal, Instance, log2_int

from litex.build.generic_platform import tools
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.cpu_interface import get_csr_header
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi

# SoC Cyclone V ------------------------------------------------------------------------------------

class SoCCycloneV(SoCCore):

    hps_name = "hps_0"
    def __init__(self, platform, clk_freq, **kwargs):
        SoCCore.__init__(self, platform, clk_freq, cpu_type=None, **kwargs)

        # CycloneV (Minimal) ----------------------------------------------------------------------------
        fclk_reset0_n = Signal()

        hps_pads = platform.request("hps")
        hps_ddram_pads = platform.request("hps_ddram")

        self.hps_params = dict(
            i_key   = hps_pads.nrst,
            o_hps_io_gpio_inst_GPIO53 = hps_pads.led,
            i_hps_io_gpio_inst_GPIO54 = hps_pads.key,
            io_hps_io_gpio_inst_GPIO40 = hps_pads.ltc_gpio,
            io_hps_io_gpio_inst_GPIO61 = hps_pads.gsensor_int,
            io_hps_io_gpio_inst_GPIO48 = hps_pads.i2c_control,

            # HPS ddram
            o_mem_a         = hps_ddram_pads.a,
            o_mem_ba        = hps_ddram_pads.ba,
            o_mem_ck        = hps_ddram_pads.ck_p,
            o_mem_ck_n      = hps_ddram_pads.ck_n,
            o_mem_cke       = hps_ddram_pads.cke,
            o_mem_cs_n      = hps_ddram_pads.cs_n,
            o_mem_ras_n     = hps_ddram_pads.ras_n,
            o_mem_cas_n     = hps_ddram_pads.cas_n,
            o_mem_we_n      = hps_ddram_pads.we_n,
            o_mem_reset_n   = hps_ddram_pads.reset_n,
            io_mem_dq       = hps_ddram_pads.dq,
            io_mem_dqs      = hps_ddram_pads.dqs_p,
            io_mem_dqs_n    = hps_ddram_pads.dqs_n,
            o_mem_odt       = hps_ddram_pads.odt,
            o_mem_dm        = hps_ddram_pads.dm,
            i_oct_rzqin     = hps_ddram_pads.rzq,

            # Bridges clk/rst
            i_clk_clk = ClockSignal("sys"),
            i_reset_reset_n = fclk_reset0_n,
            # clk/rst
            # TODO: add reset syncrhonizer to hps_0?
            # TODO: add rst_req signals inside hps_0? these are created with pulse detectors
            # i_clk   = hps_pads.clk, # must connect to the
            i_npor  = hps_pads.npor,
            i_nrst  = hps_pads.nrst,
            # o_h2f_rst_n,                //           h2f_reset.reset_n
            # i_f2h_cold_rst_req_n,       //  f2h_cold_reset_req.reset_n
            # i_f2h_dbg_rst_req_n,        // f2h_debug_reset_req.reset_n
            # i_f2h_warm_rst_req_n,       //  f2h_warm_reset_req.reset_n
        )
        self.comb += ResetSignal("sys").eq(~fclk_reset0_n)
        # TODO: how to call hps ip? where is it? name? extension?
        # everything we need to build the hps ip is under
        # ${QUARTUS_ROOTDIR}/../ip/altera/hps
        # I need to generate a QSYS file for the HPS
        platform.add_ip(os.path.join("ip", self.hps_name + ".qsys"))

        self.add_hps_peripherials(platform)
        self.add_hps_fpga_interfaces()

    # HPS peripherials -----------------------------------------------------------------------------

    def add_hps_peripherials(self, platform):
        hps_enet_pads = platform.request("hps_enet")
        hps_usb_pads = platform.request("hps_usb")
        hps_flash_pads = platform.request("hps_flash")
        hps_sd_pads = platform.request("hps_sd")
        hps_spim_pads = platform.request("hps_spim")
        hps_uart_pads = platform.request("hps_uart")
        hps_i2c0_pads = platform.request("hps_i2c", 0)
        hps_i2c1_pads = platform.request("hps_i2c", 1)

        self.hps_params.update(
            # HPS ethernet
            o_hps_io_emac1_inst_TX_CLK = hps_enet_pads.gtx_clk,
            o_hps_io_emac1_inst_TXD0   = hps_enet_pads.tx_data[0],
            o_hps_io_emac1_inst_TXD1   = hps_enet_pads.tx_data[1],
            o_hps_io_emac1_inst_TXD2   = hps_enet_pads.tx_data[2],
            o_hps_io_emac1_inst_TXD3   = hps_enet_pads.tx_data[3],
            i_hps_io_emac1_inst_MDIO   = hps_enet_pads.mdio,
            o_hps_io_emac1_inst_MDC    = hps_enet_pads.mdc,
            i_hps_io_emac1_inst_RX_CTL = hps_enet_pads.rx_dv,
            o_hps_io_emac1_inst_TX_CTL = hps_enet_pads.tx_en,
            i_hps_io_emac1_inst_RX_CLK = hps_enet_pads.rx_clk,
            i_hps_io_emac1_inst_RXD0   = hps_enet_pads.rx_data[0],
            i_hps_io_emac1_inst_RXD1   = hps_enet_pads.rx_data[1],
            i_hps_io_emac1_inst_RXD2   = hps_enet_pads.rx_data[2],
            i_hps_io_emac1_inst_RXD3   = hps_enet_pads.rx_data[3],
            io_hps_io_gpio_inst_GPIO35 = hps_enet_pads.int_n,

            # HPS QSPI
            io_hps_io_qspi_inst_IO0 = hps_flash_pads.data[0],
            io_hps_io_qspi_inst_IO1 = hps_flash_pads.data[1],
            io_hps_io_qspi_inst_IO2 = hps_flash_pads.data[2],
            io_hps_io_qspi_inst_IO3 = hps_flash_pads.data[3],
            o_hps_io_qspi_inst_SS0  = hps_flash_pads.ncso,
            o_hps_io_qspi_inst_CLK  = hps_flash_pads.dclk,

            # HPS SD card
            o_hps_io_sdio_inst_CLK  = hps_sd_pads.clk,
            io_hps_io_sdio_inst_CMD = hps_sd_pads.cmd,
            io_hps_io_sdio_inst_D0  = hps_sd_pads.data[0],
            io_hps_io_sdio_inst_D1  = hps_sd_pads.data[1],
            io_hps_io_sdio_inst_D2  = hps_sd_pads.data[2],
            io_hps_io_sdio_inst_D3  = hps_sd_pads.data[3],

            # HPS USB
            io_hps_io_usb1_inst_D0  = hps_usb_pads.data[0],
            io_hps_io_usb1_inst_D1  = hps_usb_pads.data[1],
            io_hps_io_usb1_inst_D2  = hps_usb_pads.data[2],
            io_hps_io_usb1_inst_D3  = hps_usb_pads.data[3],
            io_hps_io_usb1_inst_D4  = hps_usb_pads.data[4],
            io_hps_io_usb1_inst_D5  = hps_usb_pads.data[5],
            io_hps_io_usb1_inst_D6  = hps_usb_pads.data[6],
            io_hps_io_usb1_inst_D7  = hps_usb_pads.data[7],
            o_hps_io_usb1_inst_STP  = hps_usb_pads.stp,
            i_hps_io_usb1_inst_CLK  = hps_usb_pads.clkout,
            i_hps_io_usb1_inst_DIR  = hps_usb_pads.dir,
            i_hps_io_usb1_inst_NXT  = hps_usb_pads.nxt,

            # HPS SPI
            o_hps_io_spim1_inst_CLK  = hps_spim_pads.clk,
            o_hps_io_spim1_inst_MOSI = hps_spim_pads.mosi,
            i_hps_io_spim1_inst_MISO = hps_spim_pads.miso,
            io_hps_io_spim1_inst_SS0 = hps_spim_pads.ss,

            # HPS UART
            io_hps_io_gpio_inst_GPIO09 = hps_uart_pads.conv_usb_n,
            i_hps_io_uart0_inst_RX     = hps_uart_pads.rx,
            o_hps_io_uart0_inst_TX     = hps_uart_pads.tx,

            # HPS I2C0
            io_hps_io_i2c0_inst_SDA = hps_i2c0_pads.sdat,
            io_hps_io_i2c0_inst_SCL = hps_i2c0_pads.sclk,

            # HPS I2C1
            io_hps_io_i2c1_inst_SDA = hps_i2c1_pads.sdat,
            io_hps_io_i2c1_inst_SCL = hps_i2c1_pads.sclk,
        )

    # HPS-FPGA interfaces --------------------------------------------------------------------------

    def add_hps_fpga_interfaces(self):
        # self.add_f2h_axi()
        self.add_h2f_axi()
        self.add_h2f_axi_lw()

    # FPGA-2-HPS AXI -------------------------------------------------------------------------------

    def add_f2h_axi(self): # TODO id width????
        self.f2h_axi = f2h_axi = axi.AXIInterface(data_width=64, address_width=32, id_width=8)
        self.add_wishbone_to_axi(f2h_axi, base_address=0x43c00000) # TODO: address??
        self.hps_params.update(
            # f2h_axi clk
            i_f2h_axi_clk = ClockSignal("sys"),

            # f2h_axi aw
            i_f2h_AWVALID = f2h_axi.aw.valid,
            o_f2h_AWREADY = f2h_axi.aw.ready,
            i_f2h_AWADDR  = f2h_axi.aw.addr,
            i_f2h_AWBURST = f2h_axi.aw.burst,
            i_f2h_AWLEN   = f2h_axi.aw.len,
            i_f2h_AWSIZE  = f2h_axi.aw.size,
            i_f2h_AWID    = f2h_axi.aw.id,
            i_f2h_AWLOCK  = f2h_axi.aw.lock,
            i_f2h_AWPROT  = f2h_axi.aw.prot,
            i_f2h_AWCACHE = f2h_axi.aw.cache,
            i_f2h_AWUSER  = f2h_axi.aw.user,

            # f2h_axi w
            i_f2h_WVALID = f2h_axi.w.valid,
            i_f2h_WLAST  = f2h_axi.w.last,
            o_f2h_WREADY = f2h_axi.w.ready,
            i_f2h_WID    = f2h_axi.w.id,
            i_f2h_WDATA  = f2h_axi.w.data,
            i_f2h_WSTRB  = f2h_axi.w.strb,

            # f2h_axi b
            o_f2h_BVALID = f2h_axi.b.valid,
            i_f2h_BREADY = f2h_axi.b.ready,
            o_f2h_BID    = f2h_axi.b.id,
            o_f2h_BRESP  = f2h_axi.b.resp,

            # f2h_axi ar
            i_f2h_ARVALID = f2h_axi.ar.valid,
            o_f2h_ARREADY = f2h_axi.ar.ready,
            i_f2h_ARADDR  = f2h_axi.ar.addr,
            i_f2h_ARBURST = f2h_axi.ar.burst,
            i_f2h_ARLEN   = f2h_axi.ar.len,
            i_f2h_ARID    = f2h_axi.ar.id,
            i_f2h_ARLOCK  = f2h_axi.ar.lock,
            i_f2h_ARSIZE  = f2h_axi.ar.size,
            i_f2h_ARPROT  = f2h_axi.ar.prot,
            i_f2h_ARCACHE = f2h_axi.ar.cache,
            i_f2h_ARUSER  = f2h_axi.ar.user,

            # f2h_axi r
            o_f2h_RVALID = f2h_axi.r.valid,
            i_f2h_RREADY = f2h_axi.r.ready,
            o_f2h_RLAST  = f2h_axi.r.last,
            o_f2h_RID    = f2h_axi.r.id,
            o_f2h_RRESP  = f2h_axi.r.resp,
            o_f2h_RDATA  = f2h_axi.r.data,

        )

    # HPS-2-FPGA AXI -------------------------------------------------------------------------------

    def add_h2f_axi(self): # TODO id width????
        self.h2f_axi = h2f_axi = axi.AXIInterface(data_width=64, address_width=32, id_width=8)
        self.add_axi_to_wishbone(h2f_axi, base_address=0x43d00000) # TODO: address??
        self.hps_params.update(
            # h2f_axi clk
            i_h2f_axi_clk = ClockSignal("sys"),

            # h2f_axi aw
            o_h2f_AWVALID = h2f_axi.aw.valid,
            i_h2f_AWREADY = h2f_axi.aw.ready,
            o_h2f_AWADDR  = h2f_axi.aw.addr,
            o_h2f_AWBURST = h2f_axi.aw.burst,
            o_h2f_AWLEN   = h2f_axi.aw.len,
            o_h2f_AWSIZE  = h2f_axi.aw.size,
            o_h2f_AWID    = h2f_axi.aw.id,
            o_h2f_AWLOCK  = h2f_axi.aw.lock,
            o_h2f_AWPROT  = h2f_axi.aw.prot,
            o_h2f_AWCACHE = h2f_axi.aw.cache,
            o_h2f_AWQOS   = h2f_axi.aw.qos,

            # h2f_axi w
            o_h2f_WVALID = h2f_axi.w.valid,
            o_h2f_WLAST  = h2f_axi.w.last,
            i_h2f_WREADY = h2f_axi.w.ready,
            o_h2f_WID    = h2f_axi.w.id,
            o_h2f_WDATA  = h2f_axi.w.data,
            o_h2f_WSTRB  = h2f_axi.w.strb,

            # h2f_axi b
            i_h2f_BVALID = h2f_axi.b.valid,
            o_h2f_BREADY = h2f_axi.b.ready,
            i_h2f_BID    = h2f_axi.b.id,
            i_h2f_BRESP  = h2f_axi.b.resp,

            # h2f_axi ar
            o_h2f_ARVALID = h2f_axi.ar.valid,
            i_h2f_ARREADY = h2f_axi.ar.ready,
            o_h2f_ARADDR  = h2f_axi.ar.addr,
            o_h2f_ARBURST = h2f_axi.ar.burst,
            o_h2f_ARLEN   = h2f_axi.ar.len,
            o_h2f_ARID    = h2f_axi.ar.id,
            o_h2f_ARLOCK  = h2f_axi.ar.lock,
            o_h2f_ARSIZE  = h2f_axi.ar.size,
            o_h2f_ARPROT  = h2f_axi.ar.prot,
            o_h2f_ARCACHE = h2f_axi.ar.cache,
            o_h2f_ARQOS   = h2f_axi.ar.qos,

            # h2f_axi r
            i_h2f_RVALID = h2f_axi.r.valid,
            o_h2f_RREADY = h2f_axi.r.ready,
            i_h2f_RLAST  = h2f_axi.r.last,
            i_h2f_RID    = h2f_axi.r.id,
            i_h2f_RRESP  = h2f_axi.r.resp,
            i_h2f_RDATA  = h2f_axi.r.data,
        )

    # HPS-2-FPGA AXI ligth-weight ------------------------------------------------------------------

    def add_h2f_axi_lw(self):
        self.h2f_axi_lw = h2f_axi_lw = axi.AXILiteInterface(data_width=32, address_width=32)
        self.add_axi_lw_to_wishbone(h2f_axi_lw, base_address=0x43e00000) # TODO: address??
        # TODO: Are constant values OK?
        self.hps_params.update(
            # h2f_lw_axi clk
            i_h2f_lw_axi_clk = ClockSignal("sys"),

            # h2f_lw aw
            i_h2f_lw_AWVALID = h2f_axi_lw.aw.valid,
            o_h2f_lw_AWREADY = h2f_axi_lw.aw.ready,
            i_h2f_lw_AWADDR  = h2f_axi_lw.aw.addr,
            i_h2f_lw_AWBURST = 1,
            i_h2f_lw_AWLEN   = 1,
            i_h2f_lw_AWSIZE  = 32,
            i_h2f_lw_AWID    = 1,
            i_h2f_lw_AWLOCK  = 0,
            i_h2f_lw_AWPROT  = 0,
            i_h2f_lw_AWCACHE = 0,

            # h2f_lw w
            i_h2f_lw_WVALID = h2f_axi_lw.w.valid,
            i_h2f_lw_WLAST  = h2f_axi_lw.w.last,
            o_h2f_lw_WREADY = h2f_axi_lw.w.ready,
            i_h2f_lw_WID    = 1,
            i_h2f_lw_WDATA  = h2f_axi_lw.w.data,
            i_h2f_lw_WSTRB  = h2f_axi_lw.w.strb,

            # h2f_lw b
            o_h2f_lw_BVALID = h2f_axi_lw.b.valid,
            i_h2f_lw_BREADY = h2f_axi_lw.b.ready,
            o_h2f_lw_BID    = 1,
            o_h2f_lw_BRESP  = h2f_axi_lw.b.resp,

            # h2f_lw ar
            i_h2f_lw_ARVALID = h2f_axi_lw.ar.valid,
            o_h2f_lw_ARREADY = h2f_axi_lw.ar.ready,
            i_h2f_lw_ARADDR  = h2f_axi_lw.ar.addr,
            i_h2f_lw_ARBURST = 1,
            i_h2f_lw_ARLEN   = 1,
            i_h2f_lw_ARSIZE  = 32,
            i_h2f_lw_ARID    = 1,
            i_h2f_lw_ARLOCK  = 0,
            i_h2f_lw_ARPROT  = 0,
            i_h2f_lw_ARCACHE = 0,

            # h2f_lw r
            o_h2f_lw_RVALID = h2f_axi_lw.r.valid,
            i_h2f_lw_RREADY = h2f_axi_lw.r.ready,
            o_h2f_lw_RLAST  = h2f_axi_lw.r.last,
            o_h2f_lw_RID    = 1,
            o_h2f_lw_RRESP  = h2f_axi_lw.r.resp,
            o_h2f_lw_RDATA  = h2f_axi_lw.r.data,

        )

    # TODO: what addres to use?
    def add_wishbone_to_axi(self, axi_port, base_address=0x43c00000):
        wb = wishbone.Interface(data_width=axi_port.data_width, adr_width=axi_port.address_width)
        wishbone2axi = axi.Wishbone2AXI(wb, axi_port, base_address)
        self.submodules += wishbone2axi
        self.add_wb_slave(wb)

    def add_axi_to_wishbone(self, axi_port, base_address=0x43c00000):
        wishbone_adr_shift = log2_int(axi_port.data_width//8)
        wb = wishbone.Interface(data_width=axi_port.data_width, adr_width=axi_port.address_width-wishbone_adr_shift)
        axi2wishbone = axi.AXI2Wishbone(axi_port, wb, base_address)
        self.submodules += axi2wishbone
        self.add_wb_master(wb)

    def add_axi_lw_to_wishbone(self, axi_port, base_address=0x43c00000):
        wishbone_adr_shift = log2_int(axi_port.data_width//8)
        wb = wishbone.Interface(data_width=axi_port.data_width, adr_width=axi_port.address_width-wishbone_adr_shift)
        axilw2wishbone = axi.AXILite2Wishbone(axi_port, wb, base_address)
        self.submodules += axilw2wishbone
        self.add_wb_master(wb)

    def do_finalize(self):
        SoCCore.do_finalize(self)
        self.specials += Instance(self.hps_name, **self.hps_params)

    def generate_software_header(self, filename):
        csr_header = get_csr_header(self.csr_regions,
                                    self.constants,
                                    with_access_functions=False)
        tools.write_to_file(filename, csr_header)
