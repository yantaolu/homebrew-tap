class CodexSwitch < Formula
  desc "Switch local Codex accounts and Responses-compatible providers"
  homepage "https://github.com/yantaolu/codex-switch"
  license "MIT"

  depends_on :macos

  if Hardware::CPU.arm?
    url "https://github.com/yantaolu/codex-switch/releases/download/v1.0.1/codex-switch_1.0.1_darwin_arm64.tar.gz"
    sha256 "59618ca9f93b9f2a1757dbb9ba9960867626e0692fdd94b91da81432e76dbc62"
  end

  if Hardware::CPU.intel?
    url "https://github.com/yantaolu/codex-switch/releases/download/v1.0.1/codex-switch_1.0.1_darwin_amd64.tar.gz"
    sha256 "11cfe7690d2d47cb1c9c57b78a14e93319f5969ba706ca25f571765f322de1a0"
  end

  # Older Homebrew can detect the architecture suffix as the package version.
  version "1.0.1" if Version.detect(stable.url).to_s != "1.0.1"

  def install
    bin.install "codex-switch"
    doc.install "README.md", "CHANGELOG.md", "LICENSE", "docs"
    pkgshare.install "modules.json", "licenses"
  end

  def caveats
    <<~EOS
      Run codex-switch to manage accounts. Switching leaves clients stopped.
      Codex CLI is needed for login, switching, usage and native session forks.
      Account data and Keychain entries are retained on uninstall.
      After upgrading an older helper-based setup, run codex-switch doctor;
      use codex-switch use <ID> to rewrite its verified stable helper path.
    EOS
  end

  test do
    assert_equal version.to_s, shell_output("#{bin}/codex-switch version").strip
    assert_match "codex-switch", shell_output("#{bin}/codex-switch --help")
    assert_match "--force", shell_output("#{bin}/codex-switch use --help")
  end
end
