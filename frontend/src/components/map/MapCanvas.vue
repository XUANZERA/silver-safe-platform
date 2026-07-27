<template>
  <div 
    id="map"
    class="map-container"
  ></div>
</template>




<script setup>

import { onMounted } from "vue"
import AMapLoader from "@amap/amap-jsapi-loader"
import elderIcon from "./elder.png"

onMounted(() => {
  AMapLoader.load({
    key: "3e07748490342e12fb42d63b84f7b658",
    version: "2.0",
  }).then((AMap) => {

    const map = new AMap.Map("map", {
      zoom: 15,
      center: [
        113.2644,
        23.1291
      ]
    })
    
    const markerImage = document.createElement("img")
    markerImage.src = elderIcon
    markerImage.alt = "elder marker"
    markerImage.width = 36
    markerImage.height = 36
    markerImage.style.display = "block"
    markerImage.style.width = "36px"
    markerImage.style.height = "36px"
    markerImage.style.maxWidth = "none"
    markerImage.style.objectFit = "contain"

    const marker = new AMap.Marker({
        position:[
            113.2644,
            23.1291
        ],
        content: markerImage,
        anchor: "bottom-center"
    })

    marker.setMap(map)
  })
})





</script>
<style scoped>

.map-container {
  width:100%;
  height:600px;
}

</style>
