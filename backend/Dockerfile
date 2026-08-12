FROM node:20-alpine

WORKDIR /usr/src/app

# install git (simple-git uses the git binary)
RUN apk add --no-cache git openssh

COPY package.json package-lock.json* ./

RUN npm ci --production

COPY . .

EXPOSE 4000
CMD ["node","src/index.js"]
