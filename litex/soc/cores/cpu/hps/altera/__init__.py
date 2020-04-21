from litex.soc.cores.cpu.hps.altera.cyclonev import CycloneV

def AlteraHPSDecoder(platform, variant):
    assert platform.device.startswith("5C") or platform.device.startswith("5S"), "Only Cyclone V and Stratix V Devices supported"
    return CycloneV(platform, variant)
