// SPDX-License-Identifier: GPL-2.0-only
/*
 * wrreg: write one 32-bit register through /dev/mem, for bring-up.
 *
 * Only safe for blocks whose clocks are already running: reading or writing an
 * unclocked display or LPASS register from Linux hangs the phone.
 *
 *   wrreg <phys> <value>
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
	volatile uint32_t *p;
	unsigned long phys, page, off;
	int fd;

	if (argc < 3) {
		fprintf(stderr, "usage: %s <phys> <value>\n", argv[0]);
		return 2;
	}
	phys = strtoul(argv[1], NULL, 0);

	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) {
		perror("/dev/mem");
		return 1;
	}

	page = phys & ~0xfffUL;
	p = mmap(NULL, 0x2000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, page);
	if (p == MAP_FAILED) {
		perror("mmap");
		return 1;
	}

	off = (phys & 0xfff) / 4;
	printf("before: %#010lx = %#010x\n", phys, p[off]);
	p[off] = strtoul(argv[2], NULL, 0);
	__sync_synchronize();
	printf("after:  %#010lx = %#010x\n", phys, p[off]);

	return 0;
}
