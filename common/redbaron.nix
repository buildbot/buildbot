with import <nixpkgs> { };
pkgs.mkShell {
  buildInputs = [
    python3
    ripgrep
    (python3Packages.redbaron.override {
      baron = python3Packages.baron.overrideAttrs (oldAttrs: {
        patches = [
          # https://github.com/PyCQA/baron/pull/179
          (pkgs.fetchpatch {
            url = "https://github.com/PyCQA/baron/commit/3c9d83ca54dcbc5c88b3963c6a79804fe154c0a5.patch";
            sha256 = "sha256-vLfu9DurvsU7A7kYMW78n/ogXd1bJGEjUevUYZiQCHk=";
          })
        ];
      });
    })
  ];
}
