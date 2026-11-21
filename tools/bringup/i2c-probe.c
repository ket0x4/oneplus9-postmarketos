// SPDX-License-Identifier: GPL-2.0-only
/*
 * i2c-probe: read from an i2c address and report what happened. Built static
 * for the phone, which has no tooling yet.
 *
 *   i2c-probe <bus> <addr> [reg]
 */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>

#define I2C_RDWR 0x0707
#define I2C_M_RD 0x0001

struct i2c_msg {
	unsigned short addr;
	unsigned short flags;
	unsigned short len;
	unsigned char *buf;
};

struct i2c_rdwr_ioctl_data {
	struct i2c_msg *msgs;
	unsigned int nmsgs;
};

int main(int argc, char **argv)
{
	char path[32], buf[8] = {0};
	struct i2c_msg msg;
	struct i2c_rdwr_ioctl_data d;
	unsigned char reg;
	int fd, ret;

	if (argc < 3) {
		fprintf(stderr, "usage: %s <bus> <addr> [reg]\n", argv[0]);
		return 2;
	}

	snprintf(path, sizeof(path), "/dev/i2c-%s", argv[1]);
	fd = open(path, O_RDWR);
	if (fd < 0) {
		perror(path);
		return 1;
	}

	msg.addr = strtoul(argv[2], NULL, 16);
	msg.flags = I2C_M_RD;
	msg.len = 1;
	msg.buf = buf;

	if (argc > 3) {
		/* write the register address, then read one byte back */
		reg = strtoul(argv[3], NULL, 16);
		msg.flags = 0;
		msg.len = 1;
		msg.buf = &reg;
		d.msgs = &msg;
		d.nmsgs = 1;
		if (ioctl(fd, I2C_RDWR, &d) < 0) {
			printf("write reg %#x: FAIL %s\n", reg, strerror(errno));
			return 1;
		}
		msg.flags = I2C_M_RD;
	}

	d.msgs = &msg;
	d.nmsgs = 1;
	ret = ioctl(fd, I2C_RDWR, &d);
	if (ret < 0) {
		printf("read addr %#x: FAIL %s\n", msg.addr, strerror(errno));
		return 1;
	}
	printf("read addr %#x: OK -> %#04x\n", msg.addr, buf[0]);
	return 0;
}
