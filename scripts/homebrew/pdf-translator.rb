class PdfTranslator < Formula
  include Language::Python::Virtualenv

  desc "Translate PDF documents with pluggable LLM backends, preserving layout"
  homepage "https://github.com/babyworm/pdf-translator"
  url "https://github.com/babyworm/pdf-translator/archive/refs/tags/v2.1.0.tar.gz"
  sha256 "" # Update with actual SHA256 after release
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      Java 11+ is required for PDF extraction:
        brew install openjdk@21

      Optional — OCR support:
        brew install tesseract

      Verify installation:
        pdf-translator check-deps
    EOS
  end

  test do
    assert_match "check-deps", shell_output("#{bin}/pdf-translator --help", 2)
  end
end
