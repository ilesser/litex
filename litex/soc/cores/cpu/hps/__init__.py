from litex.build.altera.platform import AlteraPlatform
from litex.soc.cores.cpu.hps.altera import AlteraHPSDecoder

def HPSDecoder(platform, variant):
    assert AlteraPlatform in type(platform).__bases__, "Only Altera HPS are supported"
    return AlteraHPSDecoder(platform, variant)
