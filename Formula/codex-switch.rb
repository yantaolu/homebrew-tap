class CodexSwitch < Formula
  desc "Switch local Codex accounts and Responses-compatible providers"
  homepage "https://github.com/yantaolu/codex-switch"
  license "MIT"

  depends_on :macos

  if Hardware::CPU.arm?
    url "https://github.com/yantaolu/codex-switch/releases/download/v1.0.0/codex-switch_1.0.0_darwin_arm64.tar.gz"
    sha256 "cc850f5c9b6916ccf906422f6a320b7fce72eb4366675191f497d0a76b2ddff4"
  end

  if Hardware::CPU.intel?
    url "https://github.com/yantaolu/codex-switch/releases/download/v1.0.0/codex-switch_1.0.0_darwin_amd64.tar.gz"
    sha256 "2b4e4fc3fa1b30a23b1ba3ea71fd95b0d608bbb5320b7c0a8a3cc2b89d80fa9d"
  end

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
