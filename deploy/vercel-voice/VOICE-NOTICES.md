# Voice attribution

The self-hosted natural female voice uses Kokoro-82M's `af_heart` voice.

- Model publisher: hexgrad, https://huggingface.co/hexgrad/Kokoro-82M
- Model license: Apache License 2.0, https://www.apache.org/licenses/LICENSE-2.0
- ONNX conversion/runtime: thewh1teagle/kokoro-onnx,
  https://github.com/thewh1teagle/kokoro-onnx (MIT license).
- Quantized model and voice weights are downloaded from the publisher's pinned
  `model-files-v1.0` release into temporary runtime storage; they are not in Git.
- Kokoro's phonemizer uses the espeak-ng library supplied by espeakng-loader;
  its package includes the upstream licensing notices.

The application does not claim that these synthetic voices are real people.
