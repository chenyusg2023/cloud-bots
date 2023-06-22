#! /usr/bin/env groovy

pipeline {

  agent any
  environment {
    SPECTRAL_DSN = 'https://spu-f641f73b9c03467eb3544c4095b3d04e@get.spectralops.io'
  }
  stages {
    stage('install Spectral') {
      steps {
        sh "curl -L 'https://get.spectralops.io/latest/x/sh?key=spu-f641f73b9c03467eb3544c4095b3d04e' | sh"
      }
    }
    stage('scan for issues') {
      steps {
        sh " $HOME/.spectral/spectral scan --engines oss"
      }
    }
  }
}
