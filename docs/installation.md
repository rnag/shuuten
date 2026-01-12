# Installation

## Stable release

To install Shuuten Signal, run this command in your terminal:

```sh
uv add shuuten
# For SES email outside AWS Lambda:
uv add "shuuten[email]"
```

Or if you prefer to use `pip`:

```sh
pip install shuuten
# For SES email outside AWS Lambda:
pip install "shuuten[email]"
```

## From source

The source files for Shuuten Signal can be downloaded from the [Github repo](https://github.com/rnag/shuuten).

You can either clone the public repository:

```sh
git clone git://github.com/rnag/shuuten
```

Or download the [tarball](https://github.com/rnag/shuuten/tarball/master):

```sh
curl -OJL https://github.com/rnag/shuuten/tarball/master
```

Once you have a copy of the source, you can install it with:

```sh
cd shuuten
uv pip install .
```
