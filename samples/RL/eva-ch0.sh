ulimit -c 0
# Resnet-18 FV size 256
# Debug Load Pretrain (icm.IntrinsicCuriosityModule.load_pretrain)
# Note: this is done through hacking pretrain-d, not by changing parameters
NAME=Vision-Formula-1-DLP
OUT=evaluation/$NAME/
mkdir -p $OUT

./pretrain-d.sh --visionformula 1 \
	--ckptdir ackpt/Vision-Formula-1-FEAT-256/ \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 1024 \
	--eval \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 1048576 \
	--samplebatching 16 \
	--samplebase 1048576 > evaluation/$NAME.out

exit

# Resnet-18 FV size 256
# New Samples (Randomly Generated)
NAME=Vision-Formula-1-reg-NS
OUT=evaluation/$NAME/
mkdir -p $OUT

./pretrain-d.sh --visionformula 1 \
	--ckptdir ackpt/Vision-Formula-1-FEAT-256/ \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 1024 \
	--eval \
	--sampletouse 1024 \
	--samplebatching 16 \
	> evaluation/$NAME.out

exit

# Resnet-18 FV size 256
# Regression test (we cannot reproduce 9*% accuracy with curiosity-rl.py
NAME=Vision-Formula-1-reg
OUT=evaluation/$NAME/
mkdir -p $OUT

./pretrain-d.sh --visionformula 1 \
	--ckptdir ackpt/Vision-Formula-1-FEAT-256/ \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 1048576 \
	--eval \
	--mispout $OUT \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 1048576 \
	--samplebatching 16 \
	--samplebase 1048576 > evaluation/$NAME.out

exit

# Resnet-18 FV size 256
# 
OUT=evaluation/Vision-Formula-1/
mkdir -p $OUT

./pretrain-d.sh --ferev 11 --elu \
	--ckptdir ackpt/Vision-Formula-1-FEAT-256/ --ckptprefix formula-1 \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 1048576 \
	--eval \
	--mispout $OUT \
	--visionformula 1 \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 1048576 \
	--samplebatching 16 \
	--samplebase 1048576 > evaluation/Vision-Formula-1.out

exit

# Resnet-18 FV size 256
# 
OUT=evaluation/Resnet-SMView-of-6-A12-Rev-11-MISP-256/ 
mkdir -p $OUT

./pretrain-d.sh --ferev 11 --elu \
	--ckptdir ackpt/Resnet-View-0-of-14-Action12-Rev-11-Feat-256-524288-fixcam/ --ckptprefix working-try11 \
	--batch 2 --queuemax 64 --threads 1 \
	--avi \
	--res 224 \
	--iter 524288 \
	--eval \
	--mispout $OUT \
	--sharedmultiview \
	--viewset cube \
	--featnum 256 \
	--imhidden 256 256 \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 524288 \
	--samplebatching 64 \
	--samplebase 1048576 > evaluation/Resnet-SMView-of-6-Rev-11-Feat-256-524288-fixcam.out

# Resnet-18 FV size 512
# 
OUT=evaluation/Resnet-SMView-of-6-A12-Rev-11-MISP-512/ 
mkdir -p $OUT

./pretrain-d.sh --ferev 11 --elu \
	--ckptdir ackpt/Resnet-View-0-of-14-Action12-Rev-11-Feat-512-524288-fixcam/ --ckptprefix working-try11 \
	--batch 2 --queuemax 64 --threads 1 \
	--avi \
	--res 224 \
	--iter 524288 \
	--eval \
	--mispout $OUT \
	--sharedmultiview \
	--viewset cube \
	--featnum 512 \
	--imhidden 512 512 \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 524288 \
	--samplebatching 64 \
	--samplebase 1048576 > evaluation/Resnet-SMView-of-6-Rev-11-Feat-512-524288-fixcam.out

exit
# Evaluate naive rev 5

./pretrain-d.sh --ferev 5 --elu \
	--ckptdir ackpt/View-0-of-14-Action12-Rev-5-Feat-2048-524288 --ckptprefix working-try11 \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 524288 \
	--eval \
	--view 0 \
	--featnum 2048 \
	--imhidden 2048 2048 \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 524288 \
	--samplebatching 64 \
	--samplebase 1048576 > evaluation/View-0-of-14-Rev-5-Feat-2048-524288.out

exit

# More training iteratinos

./pretrain-d.sh --ferev 5 --elu \
	--eval \
	--ckptdir ackpt/View-0-of-14-Action12-Rev-5-Feat-2048-524288-Pass2/ \
	--ckptprefix working- \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 524288 \
	--view 0 \
	--featnum 2048 \
	--imhidden 2048 2048 \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M/ \
	--sampletouse 524288 \
	--samplebatching 64 \
	--samplebase 1048576 > evaluation/View-0-of-14-Rev-5-Feat-2048-524288-Pass2.out

exit

# Larger action magnitude (8x)

./pretrain-d.sh --ferev 5 --elu \
	--eval \
	--ckptdir ackpt/View-0-of-14-Action12-Rev-5-Feat-2048-524288-8thAMAG \
	--ckptprefix working-try11 \
	--batch 2 --queuemax 64 --threads 1 \
	--iter 524288 \
	--view 0 \
	--featnum 2048 \
	--imhidden 2048 2048 \
	--samplein sample/batch2-view14-norgbd-T6-R6-2M-8thAMAG/ \
	--sampletouse 524288 \
	--samplebatching 64 \
	--samplebase 1048576 > evaluation/View-0-of-14-Rev-5-Feat-2048-524288-8thAMAG.out
