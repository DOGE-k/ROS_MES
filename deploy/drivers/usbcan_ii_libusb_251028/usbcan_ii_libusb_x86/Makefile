all: clean test
test:
	$(CC) -o test test.c -L. -L.. -lpthread  -lusbcan
clean:
	rm -vf test
