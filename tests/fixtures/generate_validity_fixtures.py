"""Regenerate small, deterministic X3P validity-mask conformance fixtures.

The mask is hand specified as 0x95, 0xFD. OpenGPS ValidBuffer::IsValid uses
bit (index % 8), least-significant first. The unused final six bits are set,
matching the reference writer's initial 0xFF buffer. See README.md for sources.
"""

import hashlib
import struct
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R_FIXTURES = HERE.parents[1] / "bindings/r/verityx3p/inst/extdata"
VALIDITY = bytes([0x95, 0xFD])


def build_fixture(code, values):
    binary = struct.pack(
        "<10" + {"I": "h", "L": "i", "F": "f", "D": "d"}[code], *values
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<p:ISO5436_2 xmlns:p="http://www.opengps.eu/2008/ISO5436_2">
  <Record1><Revision>ISO5436 - 2000</Revision><FeatureType>SUR</FeatureType>
    <Axes>
      <CX><AxisType>I</AxisType><Increment>0.25</Increment><Offset>1</Offset></CX>
      <CY><AxisType>I</AxisType><Increment>0.5</Increment><Offset>2</Offset></CY>
      <CZ><AxisType>A</AxisType><DataType>{code}</DataType><Increment>0.5</Increment><Offset>100</Offset></CZ>
    </Axes>
  </Record1>
  <Record2><Creator>Verity synthetic validity-mask fixture</Creator></Record2>
  <Record3><MatrixDimension><SizeX>5</SizeX><SizeY>2</SizeY><SizeZ>1</SizeZ></MatrixDimension>
    <DataLink>
      <PointDataLink>bindata/data.bin</PointDataLink>
      <MD5ChecksumPointData>{hashlib.md5(binary).hexdigest()}</MD5ChecksumPointData>
      <ValidPointsLink>bindata/valid.bin</ValidPointsLink>
      <MD5ChecksumValidPoints>{hashlib.md5(VALIDITY).hexdigest()}</MD5ChecksumValidPoints>
    </DataLink>
  </Record3>
</p:ISO5436_2>
""".encode()
    path = HERE / f"validity-{code.lower()}.x3p"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in (
            ("main.xml", xml),
            ("bindata/data.bin", binary),
            ("bindata/valid.bin", VALIDITY),
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    (R_FIXTURES / path.name).write_bytes(path.read_bytes())


if __name__ == "__main__":
    build_fixture("I", list(range(-10, 0)))
    build_fixture("L", list(range(100000, 100010)))
    floats = [float(i) for i in range(10)]
    floats[2] = float("nan")  # A set mask bit must not revive a NaN height.
    build_fixture("F", floats)
    build_fixture("D", floats)
