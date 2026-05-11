<script setup lang="ts">
import { useSeo } from '@/shared/composables/useSeo'
import HomeHero from '../components/HomeHero.vue'

useSeo(() => ({
  title: '客製化數字油畫｜把照片變成可以慢慢畫的作品',
  description:
    '易木 YIIMUI — 台灣製作的客製化數字油畫平台。上傳照片，由我們轉成可以慢慢畫的編號油畫模板，附顏料、畫筆、畫布。療癒手作、紀念禮物、寵物與家人合照都適合。',
}))

import EditorLetterSection from '../components/EditorLetterSection.vue'
import LatestProductsSection from '../components/LatestProductsSection.vue'
import ThemesShowcaseSection from '../components/ThemesShowcaseSection.vue'
import FeaturedSeriesSection from '../components/FeaturedSeriesSection.vue'
import ProcessStepsSection from '../components/ProcessStepsSection.vue'
import CustomBanner from '../components/CustomBanner.vue'
import SignatureFooter from '../components/SignatureFooter.vue'
</script>

<template>
  <!-- A. Cinematic Hero — 已是雜誌封面式 -->
  <HomeHero />

  <!-- B. Editor's Letter — 安靜窄欄引言（呼吸區） -->
  <EditorLetterSection />

  <!-- D. Latest Products — 最新上架 4 卡 -->
  <LatestProductsSection />

  <!-- E. Themes — 全寬深色 themes band（重壓底） -->
  <ThemesShowcaseSection />

  <!-- 精選系列 — 4 mood gradient（中等密度） -->
  <FeaturedSeriesSection />

  <!-- F. Process — 3 步驟大序體數字（呼吸 + 流程說明） -->
  <ProcessStepsSection />

  <!-- G. Custom Call — 半深 panel + 半圖 split（CTA） -->
  <CustomBanner />

  <!-- H. Signature — 純 typography 簽名 -->
  <SignatureFooter />
</template>
