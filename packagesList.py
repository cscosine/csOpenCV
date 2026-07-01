#!/usr/bin/env python3

print("---- Ubuntu 24.04 and 22.04----")
# Ubuntu 24.04
packages_list = [
    "libgtk-3-dev",
    "pkg-config",
    "libavcodec-dev",
    "libavformat-dev",
    "libswscale-dev",
    "libtbb12",
    "libtbb-dev",
    "libjpeg-dev",
    "libpng-dev",
    "libtiff-dev",
    "libwebp-dev",
    "libdc1394-dev",
    "python3-pip",
    "python3-numpy",
    "python3-dev",
    "gstreamer1.0*",
    "ubuntu-restricted-extras",
    "libgstreamer1.0-dev",
    "libgstreamer-plugins-base1.0-dev",
    "libopenexr-dev",
]

packages_list_unique = sorted(set(sorted(packages_list)))
for i in packages_list_unique:
    print(f"{i} ", end="")
print("")
print("")
print("")

for i in packages_list_unique:
    print(f'"{i}",')
