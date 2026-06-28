*************************************
DBI codec for Disciples Sacred Lands
*************************************
-------------------
made by HoT_PlaStiC
-------------------


This script will enable to 

	1., list iamges from any.DBI
	2., decode images from any.DBI
	3., encode images into any.DBI
	4., replace images in any.DBI

First use powershell (type powershell into directory and press enter)

In order to work you have to have pillow installed:

type:

python -m pip install pillow

enter


	1., list images:
			type: python fd_portrait_codec_v2_36.py list any.DBI

	2., decode images from any.DBI:
			type: python fd_portrait_codec_v2_36.py decode any.DBI portrék\ 

		decode all images from all .DBI in the folder:
			type: python fd_portrait_codec_v2_36.py decodeall

	(you can change the folder name (portrék\) also you can change any.DBI
	to any_mod.DBI if you would like to decode the encoded images)


	3., encode images:

		In case of UNIT.DBI:
			type: python fd_portrait_codec_v2_36.py encode CFDW0048.png UNIT.DBI
	(you can write your custom images here (CFDW0048.png is a sample image)
	Images should be 55x67 or 115x67 scaled and in PNG format while encoding into UNIT.DBI)
	(if you encode a new image it will automatically generate a new slot and code for it in case of UNIT.DBI
	(starting with GP001S00) this case no need to add name at the end of the command)

		In case of other.DBI:
			type: python fd_portrait_codec_v2_36.py encode CFDW0048.png any.DBI FD050S00
	(you can write your custom images here (CFDW0048.png is a sample image)
	(you should name your image (FD050S00 is a sample here) Please Note, that the game uses layers
	and the name determines which layer category it belongs, so you should use the encoded image
	with the correct naming!)


	4., replace images:
	python fd_portrait_codec_v2_36.py replace CFDW0048.png UNIT.DBI FD026S00

	(you can write your custom images here (CFDW0048.png is a sample image)
	Images should be 55x67 or 115x67 scaled and in PNG format while handling UNIT.DBI)
	(you can choose which original portrait you would like to replace (FD026S00 for example)


	After you encode, the script will generate an UNIT_mod.DBI file, which you can copy
	and paste into Disciples Sacred Lands Imgs1 directory, and rename it to UNIT.DBI 
	overwrite the original (make backup first!)

