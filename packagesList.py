packages_list = [
    "libgtk2.0-dev",
    "pkg-config",
    "libavcodec-dev",
    "libavformat-dev",
    "libswscale-dev",
    "libtbb12",
    "libtbb-dev",
    "libjpeg-dev",
    "libpng-dev",
    "libtiff-dev",
    "libdc1394-dev",
    "python3-pip",
    "python3-numpy",
    "python3-dev",
    "gstreamer1.0*",
    "ubuntu-restricted-extras",
    "libgstreamer1.0-dev",
    "libgstreamer-plugins-base1.0-dev",
]

packages_list_unique = set(sorted(packages_list))
for i in packages_list_unique:
    # print(f'"{i}",')
    print(f"{i} ", end="")
