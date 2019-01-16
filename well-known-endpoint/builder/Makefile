all:
	docker build -t cis_builder:latest .
	docker tag cis_builder mozillaiam/cis_builder:latest
	docker login
	docker push mozillaiam/cis_builder:latest
