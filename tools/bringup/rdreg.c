// SPDX-License-Identifier: GPL-2.0-only
/*
 * rdreg: read 32-bit registers from a physical address, for bring-up.
 * Only safe for blocks whose clocks are already running.
 *
 *   rdreg <phys> <count>
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
	volatile uint32_t *p;
	unsigned long phys, page;
	unsigned count, i;
	int fd;

	if (argc < 3) {
		fprintf(stderr, "usage: %s <phys> <count>\n", argv[0]);
		return 2;
	}
	phys = strtoul(argv[1], NULL, 0);
	count = strtoul(argv[2], NULL, 0);

	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("/dev/mem");
		return 1;
	}

	page = phys & ~0xfffUL;
	p = mmap(NULL, 0x1000 + (phys & 0xfff) + count * 4, PROT_READ,
		  MAP_SHARED, fd, page);
	if (p == MAP_FAILED) {
		perror("mmap");
		return 1;
	}

	for (i = 0; i < count; i++)
		printf("%#lx: %#010x\n", phys + i * 4, p[(phys & 0xfff) / 4 + i]);

	return 0;
}
