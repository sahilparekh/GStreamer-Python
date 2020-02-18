FROM python:3.8

RUN set -ex; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        gcc \
        gir1.2-gstreamer-1.0 \
        gir1.2-gst-plugins-base-1.0 \
        gir1.2-gtk-3.0 \
        gstreamer1.0-alsa \
        gstreamer1.0-doc \
        gstreamer1.0-gl \
        gstreamer1.0-gtk3 \
        gstreamer1.0-libav \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-pulseaudio \
        gstreamer1.0-qt5 \
        gstreamer1.0-tools \
        gstreamer1.0-x \
        libcairo2-dev \
        libgirepository1.0-dev \
        libgstreamer1.0-0 \
        pkg-config \
        python-gst-1.0; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ./main_prg.py
