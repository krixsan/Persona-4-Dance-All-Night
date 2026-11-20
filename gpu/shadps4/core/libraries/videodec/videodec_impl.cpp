// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "videodec_impl.h"

#include "common/alignment.h"
#include "common/assert.h"
#include "common/logging/log.h"
#include "video_utils.h"
#include "videodec_error.h"

#include "common/support/avdec.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>

namespace Libraries::Videodec {

static std::atomic<u32> g_decode_calls{0};
static std::atomic<u32> g_frame_logs{0};
static std::atomic<u32> g_convert_calls{0};
static std::atomic<u32> g_dump_index{0};

VdecDecoder::VdecDecoder(const OrbisVideodecConfigInfo& pCfgInfoIn,
                         const OrbisVideodecResourceInfo& pRsrcInfoIn) {
    LOG_INFO(Lib_Videodec,
             "new decoder: codec={} profile={} level={} max={}x{} dpb={} flags=0x{:x} "
             "cpu={} cpuGpu={} maxFrame={} align=0x{:x}",
             pCfgInfoIn.codecType, pCfgInfoIn.profile, pCfgInfoIn.maxLevel,
             pCfgInfoIn.maxFrameWidth, pCfgInfoIn.maxFrameHeight, pCfgInfoIn.maxDpbFrameCount,
             pCfgInfoIn.videodecFlags, pRsrcInfoIn.cpuMemorySize, pRsrcInfoIn.cpuGpuMemorySize,
             pRsrcInfoIn.maxFrameBufferSize, pRsrcInfoIn.frameBufferAlignment);

    const AVCodec* codec = avcodec_find_decoder(AV_CODEC_ID_H264);
    ASSERT(codec);

    mCodecContext = avcodec_alloc_context3(codec);
    ASSERT(mCodecContext);
    mCodecContext->width = pCfgInfoIn.maxFrameWidth;
    mCodecContext->height = pCfgInfoIn.maxFrameHeight;
    mCodecContext->flags |= AV_CODEC_FLAG_COPY_OPAQUE;

    const int open_result = avcodec_open2(mCodecContext, codec, nullptr);
    if (open_result < 0) {
        LOG_ERROR(Lib_Videodec, "avcodec_open2 failed: {}", open_result);
    }
}

VdecDecoder::~VdecDecoder() {
    avcodec_free_context(&mCodecContext);
    sws_freeContext(mSwsContext);
}

s32 VdecDecoder::Decode(const OrbisVideodecInputData& pInputDataIn,
                        OrbisVideodecFrameBuffer& pFrameBufferInOut,
                        OrbisVideodecPictureInfo& pPictureInfoOut) {
    pPictureInfoOut.isValid = false;

    if (!pInputDataIn.pAuData) {
        return ORBIS_VIDEODEC_ERROR_AU_POINTER;
    }
    if (pInputDataIn.auSize == 0) {
        return ORBIS_VIDEODEC_ERROR_AU_SIZE;
    }

    AVPacket* packet = av_packet_alloc();
    if (!packet) {
        LOG_ERROR(Lib_Videodec, "Failed to allocate packet");
        return ORBIS_VIDEODEC_ERROR_API_FAIL;
    }

    packet->data = (u8*)pInputDataIn.pAuData;
    packet->size = pInputDataIn.auSize;
    packet->pts = pInputDataIn.ptsData;
    packet->dts = pInputDataIn.dtsData;
    packet->opaque = reinterpret_cast<void*>(pInputDataIn.attachedData);

    const u32 call = g_decode_calls.fetch_add(1);
    if (call < 4) {
        LOG_INFO(Lib_Videodec, "decode #{}: au={} bytes pts={} dts={} attached=0x{:x}",
                 call, pInputDataIn.auSize, pInputDataIn.ptsData, pInputDataIn.dtsData,
                 pInputDataIn.attachedData);
    }
    if (const char* dump_dir = std::getenv("BB_VIDEODEC_DUMP")) {
        const u32 index = g_dump_index.fetch_add(1);
        if (index < 64) {
            char path[1024];
            std::snprintf(path, sizeof(path), "%s/au_%05u.h264", dump_dir, index);
            if (FILE* file = std::fopen(path, "wb")) {
                std::fwrite(packet->data, 1, packet->size, file);
                std::fclose(file);
            }
        }
    }

    int ret = avcodec_send_packet(mCodecContext, packet);
    if (ret == AVERROR_EOF) {
        // Attempt to flush buffers and try again.
        avcodec_flush_buffers(mCodecContext);
        ret = avcodec_send_packet(mCodecContext, packet);
    }
    if (ret < 0) {
        LOG_ERROR(Lib_Videodec, "Error sending packet to decoder: {}", ret);
        av_packet_free(&packet);
        return ORBIS_VIDEODEC_ERROR_API_FAIL;
    }

    AVFrame* frame = av_frame_alloc();
    if (frame == nullptr) {
        LOG_ERROR(Lib_Videodec, "Failed to allocate frame");
        av_packet_free(&packet);
        return ORBIS_VIDEODEC_ERROR_API_FAIL;
    }

    ret = avcodec_receive_frame(mCodecContext, frame);
    if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
        av_packet_free(&packet);
        av_frame_free(&frame);
        return ORBIS_OK;
    } else if (ret < 0) {
        LOG_ERROR(Lib_Videodec, "Error receiving frame from decoder: {}", ret);
        av_packet_free(&packet);
        av_frame_free(&frame);
        return ORBIS_VIDEODEC_ERROR_API_FAIL;
    }

    const u32 frame_index = g_frame_logs.fetch_add(1);
    if (frame_index < 8) {
        LOG_INFO(Lib_Videodec,
                 "decoded frame #{}: {}x{} fmt={} linesize={},{},{},{} opaque=0x{:x} pts={}",
                 frame_index, frame->width, frame->height, int(frame->format),
                 frame->linesize[0], frame->linesize[1], frame->linesize[2], frame->linesize[3],
                 reinterpret_cast<u64>(frame->opaque), frame->pts);
    }

    if (frame->format != AV_PIX_FMT_NV12) {
        AVFrame* nv12_frame = ConvertNV12Frame(*frame);
        if (!nv12_frame) {
            LOG_ERROR(Lib_Videodec, "NV12 conversion failed for {}x{} fmt={}", frame->width,
                      frame->height, int(frame->format));
            av_packet_free(&packet);
            av_frame_free(&frame);
            return ORBIS_VIDEODEC_ERROR_API_FAIL;
        }
        av_frame_free(&frame);
        frame = nv12_frame;
    }

    if (!CopyNV12Data((u8*)pFrameBufferInOut.pFrameBuffer, pFrameBufferInOut.frameBufferSize, *frame)) {
        av_frame_free(&frame);
        return ORBIS_VIDEODEC_ERROR_FRAME_BUFFER_SIZE;
    }

    const auto width = Common::AlignUp<u32>(frame->width, 16);
    const auto pitch = Common::AlignUp<u32>(frame->width, 64);
    const auto height = Common::AlignUp<u32>(frame->height, 16);

    pPictureInfoOut.isValid = true;
    pPictureInfoOut.codecType = 0;
    pPictureInfoOut.frameWidth = width;
    pPictureInfoOut.framePitch = pitch;
    pPictureInfoOut.frameHeight = height;
    pPictureInfoOut.isErrorPic = false;
    pPictureInfoOut.ptsData = frame->pts;
    pPictureInfoOut.attachedData = reinterpret_cast<u64>(frame->opaque);

    // pPictureInfoOut.codec.avc.numUnitsInTick;
    // pPictureInfoOut.codec.avc.timeScale;
    // pPictureInfoOut.codec.avc.fixedFrameRateFlag;
    // pPictureInfoOut.codec.avc.aspectRatioIdc;
    // pPictureInfoOut.codec.avc.sarWidth;
    // pPictureInfoOut.codec.avc.sarHeight;
    pPictureInfoOut.codec.avc.colourPrimaries = static_cast<u8>(frame->color_primaries);
    // pPictureInfoOut.codec.avc.transferCharacteristics;
    // pPictureInfoOut.codec.avc.matrixCoefficients;
    // pPictureInfoOut.codec.avc.videoFullRangeFlag;
    pPictureInfoOut.codec.avc.frameCropLeftOffset = 0;
    pPictureInfoOut.codec.avc.frameCropRightOffset = pitch - frame->width;
    pPictureInfoOut.codec.avc.frameCropTopOffset = 0;
    pPictureInfoOut.codec.avc.frameCropBottomOffset = height - frame->height;

    av_packet_free(&packet);
    av_frame_free(&frame);
    return ORBIS_OK;
}

s32 VdecDecoder::Flush(OrbisVideodecFrameBuffer& pFrameBufferInOut,
                       OrbisVideodecPictureInfo& pPictureInfoOut) {
    pPictureInfoOut.isValid = false;

    AVFrame* frame = av_frame_alloc();
    if (!frame) {
        LOG_ERROR(Lib_Videodec, "Failed to allocate frame");
        return ORBIS_VIDEODEC_ERROR_API_FAIL;
    }

    // avcodec_send_packet with packet set to nullptr results in codec flush.
    // This flush can produce multiple frames but we can only return one.
    // We cannot skip frames, some games hang if we do so we return only 1st.
    // Games can send multiple consecutive flushes, but ffmpeg doesn't work
    // this way and returns error. There is no way to make it flush only one
    // frame so all we can do is just ignore the result and pray.
    avcodec_send_packet(mCodecContext, nullptr);
    int ret = avcodec_receive_frame(mCodecContext, frame);
    if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
        av_frame_free(&frame);
        return ORBIS_OK;
    } else if (ret < 0) {
        LOG_ERROR(Lib_Videodec, "Error receiving frame from decoder: {}", ret);
        av_frame_free(&frame);
        return ORBIS_VIDEODEC_ERROR_API_FAIL;
    }

    if (frame->format != AV_PIX_FMT_NV12) {
        AVFrame* nv12_frame = ConvertNV12Frame(*frame);
        if (!nv12_frame) {
            LOG_ERROR(Lib_Videodec, "NV12 conversion failed for {}x{} fmt={}", frame->width,
                      frame->height, int(frame->format));
            av_frame_free(&frame);
            return ORBIS_VIDEODEC_ERROR_API_FAIL;
        }
        av_frame_free(&frame);
        frame = nv12_frame;
    }

    if (!CopyNV12Data((u8*)pFrameBufferInOut.pFrameBuffer, pFrameBufferInOut.frameBufferSize, *frame)) {
        av_frame_free(&frame);
        return ORBIS_VIDEODEC_ERROR_FRAME_BUFFER_SIZE;
    }

    const auto width = Common::AlignUp<u32>(frame->width, 16);
    const auto pitch = Common::AlignUp<u32>(frame->width, 64);
    const auto height = Common::AlignUp<u32>(frame->height, 16);

    pPictureInfoOut.isValid = true;
    pPictureInfoOut.codecType = 0;
    pPictureInfoOut.frameWidth = width;
    pPictureInfoOut.framePitch = pitch;
    pPictureInfoOut.frameHeight = height;
    pPictureInfoOut.isErrorPic = false;
    pPictureInfoOut.ptsData = frame->pts;
    pPictureInfoOut.attachedData = reinterpret_cast<u64>(frame->opaque);

    // pPictureInfoOut.codec.avc.numUnitsInTick;
    // pPictureInfoOut.codec.avc.timeScale;
    // pPictureInfoOut.codec.avc.fixedFrameRateFlag;
    // pPictureInfoOut.codec.avc.aspectRatioIdc;
    // pPictureInfoOut.codec.avc.sarWidth;
    // pPictureInfoOut.codec.avc.sarHeight;
    pPictureInfoOut.codec.avc.colourPrimaries = static_cast<u8>(frame->color_primaries);
    // pPictureInfoOut.codec.avc.transferCharacteristics;
    // pPictureInfoOut.codec.avc.matrixCoefficients;
    // pPictureInfoOut.codec.avc.videoFullRangeFlag;
    pPictureInfoOut.codec.avc.frameCropLeftOffset = 0;
    pPictureInfoOut.codec.avc.frameCropRightOffset = pitch - frame->width;
    pPictureInfoOut.codec.avc.frameCropTopOffset = 0;
    pPictureInfoOut.codec.avc.frameCropBottomOffset = height - frame->height;

    av_frame_free(&frame);
    return ORBIS_OK;
}

s32 VdecDecoder::Reset() {
    avcodec_flush_buffers(mCodecContext);
    return ORBIS_OK;
}

AVFrame* VdecDecoder::ConvertNV12Frame(AVFrame& frame) {
    const u32 convert = g_convert_calls.fetch_add(1);
    if (convert < 4) {
        LOG_INFO(Lib_Videodec, "converting frame #{}: {}x{} fmt={} data={:p},{:p},{:p}",
                 convert, frame.width, frame.height, int(frame.format),
                 static_cast<void*>(frame.data[0]), static_cast<void*>(frame.data[1]),
                 static_cast<void*>(frame.data[2]));
    }

    if (frame.width <= 0 || frame.height <= 0 || frame.format < 0 || !frame.data[0]) {
        LOG_ERROR(Lib_Videodec, "invalid source frame: {}x{} fmt={} data0={:p}", frame.width,
                  frame.height, int(frame.format), static_cast<void*>(frame.data[0]));
        return nullptr;
    }

    AVFrame* nv12_frame = av_frame_alloc();
    if (!nv12_frame) {
        LOG_ERROR(Lib_Videodec, "Failed to allocate NV12 frame");
        return nullptr;
    }
    nv12_frame->pts = frame.pts;
    nv12_frame->pkt_dts = frame.pkt_dts < 0 ? 0 : frame.pkt_dts;
    nv12_frame->format = AV_PIX_FMT_NV12;
    nv12_frame->width = frame.width;
    nv12_frame->height = frame.height;
    nv12_frame->sample_aspect_ratio = frame.sample_aspect_ratio;
    nv12_frame->crop_top = frame.crop_top;
    nv12_frame->crop_bottom = frame.crop_bottom;
    nv12_frame->crop_left = frame.crop_left;
    nv12_frame->crop_right = frame.crop_right;
    nv12_frame->opaque = frame.opaque;
    nv12_frame->color_primaries = frame.color_primaries;

    const int alloc = av_frame_get_buffer(nv12_frame, 0);
    if (alloc < 0) {
        LOG_ERROR(Lib_Videodec, "av_frame_get_buffer failed: {} (source {}x{} fmt={})",
                  av_err2str(alloc), frame.width, frame.height, int(frame.format));
        av_frame_free(&nv12_frame);
        return nullptr;
    }

    mSwsContext = sws_getCachedContext(
        mSwsContext, frame.width, frame.height, AVPixelFormat(frame.format), nv12_frame->width,
        nv12_frame->height, AV_PIX_FMT_NV12, SWS_FAST_BILINEAR, nullptr, nullptr, nullptr);
    if (!mSwsContext) {
        LOG_ERROR(Lib_Videodec, "sws_getCachedContext failed for {}x{} fmt={}", frame.width,
                  frame.height, int(frame.format));
        av_frame_free(&nv12_frame);
        return nullptr;
    }

    const auto res = sws_scale(mSwsContext, frame.data, frame.linesize, 0, frame.height,
                               nv12_frame->data, nv12_frame->linesize);
    if (res < 0) {
        LOG_ERROR(Lib_Videodec, "Could not convert to NV12: {}", av_err2str(res));
        av_frame_free(&nv12_frame);
        return nullptr;
    }

    return nv12_frame;
}

} // namespace Libraries::Videodec
