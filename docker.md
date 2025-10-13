# docker
## 官方网站
get.docker.com

## 镜像安装

**dokcker pull docker.io/library /nginx:latest**  从仓库下载镜像 

**docker --platform=xxx nginx** 下载特定cpu架构的镜像

**docker.io** 官方仓库，可以省略（在docker的.后面若为其他内容就是私有仓库，他的后面也有.io）

**library** 命名空间（作者名称）（属于官方的可以不写）

**nginx** 镜像名称

**nginx:lates**t 这个；latest表示标签，也就是版本号，latest表示最新版，一般也可以不写，默认就是最新版或最合适自己当前版本的

### docker仓库

docker仓库 hub.docker.com

镜像站

docker.fxxk.dedyn.io

#### 国内网站问题要修改镜像站点方法

**sudo vim /etc/docker/daemon.json**

容器：表示由镜像创建而来的，正在运行的

镜像：表示模具，依据他创建容器，下载到本地的

删除容器：docker rm ID (正在运行的容器进行删除 -f f表示force强制)

删除镜像：dokcer rmi ID

# docker基础指令

**docker images** 列出所有下载过的镜像

**docker rmi  id** 删除下镜像 这个id是id或者是名字(repository)

**docker run nginx**或者是id  创建并运行容器,若不存在,会直接进行创建, 然后运行,不再需要pull指令

**docker ps** 与Linux下的ps一致 查看正在运行的容器

> ​	第一个表示容器的id  每创建一个容器就会分配一个随机的id

> ​	第二个参数images表示根据哪个模具创建出来的镜像

> ​	最后一个names表示容器的名字,使用docker run创建容器时如果没有手动设置名字,系统会随机分配一个名字给他

使用**docker run** 进行时会占用窗口, 所以更加推荐使用**docker run  -d nginx**

​	-d 表示采用分离模式运行容器,会输出一个随机的序列,这个随机序列的前几位就是该容器的id

**docker run -p 80:80**  其中-p表示端口映射,将容器的80映射到主机的80端口,  (宿主机端口:容器端口)

此时容器内的localhost:80 启动 我们也能在宿主机进行访问了

### 挂在卷

**docker run -v** 挂在卷的绑定,好处是容器在删除该容器的时候数据会在本地的文件中,不会随容器的删除而删除,相当于数据持久化的保存

上述使用举例:

​	**sudo docker run -d -p 80:80 -v /website/html:/usr/share/nginx/html nginx**

​	-d : 表示分离模式，守护进程形式启动

​	-p：代表端口映射

​	-v：表示将容器的内容挂在到本地

该种方式下，因为本地的目录是新创建的为空，所以直接访问会覆盖掉容器内的目录，不显示nginx 的内容，所以采用挂载方式要在本地创建网页内容

同样的，冒号左边表示宿主机器，冒号右边是容器

像上述这样的挂在方式是**绑定挂在**   - v   宿主机目录：容器内的目录

还有一种叫做**命名挂在**，即，-v 卷的名字：容器内的目录  ，这个卷的名字是我们自己启的

eg:

​	1.创建一个挂在卷

**sudo docker volume create nginx_html**

> 这个nginx_html就是挂在卷的卷名
>
> 因此我们的创建容器就变成了

sudo docker run -d -p 80:80 -v **nginx_html**:/usr/share/nginx/html nginx

​	2.挂在卷的实际路径查看需要使用

**sudo docker volume inspect nginx_html** 

wyq@wyq:/etc/systemd/system$ sudo docker volume inspect nginx_html
[
    {
        "CreatedAt": "2025-09-23T14:04:12+08:00",
        "Driver": "local",
        "Labels": null,
        "Mountpoint": "/var/lib/docker/volumes/nginx_html/_data",
        "Name": "nginx_html",
        "Options": null,
        "Scope": "local"
    }
]

我们可以看到， 他的输出中name就是我们的挂在卷的名字，而Mountpoint就是实际挂在卷所在的宿主机的实际路径，不过我们想要查看，需要将身份切换为root才能查看

同时，使用命名挂在，docker会自动将原来的容器的index.html 进行复制在命名挂在卷的路径下，而绑定挂在就是空的，我们需要自己完成



**sudo docker volume list**  列出所有创建的卷

**sudo docker volume rm 名字**  表示删除挂在过的卷

**sudo docker volume prune -a** 删除所有没有任何容器在使用的卷

### docker run其它参数

#### docker run -e  向容器内传递环境变量

-e USERNAME=tech \  将环境变量USERNAME作为参数传递给容器内的tech变量，下同
-e PASSWORD=pswd \

以这样的方式启动了容器

那么我们在进行访问的时候，需要登陆，就可以直接使用传入的环境变量参数当作对应的参数进行使用 

**mongosh “mongodb://tech:pswd@ip:port”**



关于容器的环境变量在hub.docker.com上都有说明

#### docker run --name my_nginx nginx 给容器一个自定义的名字

这个名字要在宿主机上唯一，且使用sudo docker ps 查看到的最后一个参数names就是我们自定义的名字，这个名字与id等效

#### -it 让控制台进入容器进行交互

#### --rm 当容器停止时就删除容器

上述两个一般连用，用于临时调试一个容器

eg：

​	sudo docker run -it --rm alpine  alpine是一个轻量级的linux容器

使用该指令创建容器给我们一个可以交互的终端， exit进行退出之后，该容器也会自行删除

#### --restart 用来配置容器在停止时的启动策略

--restart  always 只要容器停止就立即重启，包括，内部崩溃，宿主机断电等

--restart unless-stopped 与always非常类似， 但是手动停止的容器，他就不会再去尝试重启

#### 其他

当我们不想使用run对容器进行创建，而是单纯对容器进行使用和暂停

**docker stop id**  暂停这个容器

**docker start id** 启动这个容器

**docker ps** 查看正在运行的容器，-a查看所有容器，包含暂停的容器

#### docker inspect id 查看docker运行时使用了哪些参数

如，有没有进行端口映射，有没有绑定挂在卷等

建议将输出的信息给ai,让他分析

#### 其他

docker pull  拉取镜像到本地

docker create 从本地镜像创建容器到本地

docker start 运行容器

docker run 拉取，创建，进行都进行

### docker logs id 查看该容器的日志

dokcer logs id -f  追踪输出 f表示follow



在容器中，每个容器都相当于是一个独立的linux操作系统，要运行的程序需要什么，就只有他想要的内容

### docker exec id 指令   采用linux 的指令操作容器

docker exec -it id /bin/sh  采用linux指令操作这个容器



## Dockerfile

用于制作镜像

现在制作一个简单的镜像

main.py

```python
from fastapi import FastAPI
import uvicorn
app=FastAPI()

@app.get("/")
def read_root():
    return {"Hello":"World"}

if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0", port=8000)
```

requirements.txt 我们需要的库名称

```TXT
fastapi
uvicorn
```

步骤：
 1. 创建Dockerfile文件，D要大些，且无后缀名

    a. dockerfile的第一行都是FROM  ，选择一个基础镜像

    ```dockerfile
    FROM python:3.13-slim
    ```

    我们希望，新建的镜像有一个python环境，可以直接到hub上面进行搜索python,我们选择的基础镜像的名称是3.12-slim，表示里面的基础镜像的python版本是3.13

    b. 切换到镜像内的一个目录

    ```dockerfile
    WORKDIR /app
    ```

    WORKDIR 有点像是cd ，切换到/app目录下，作为工作目录。往后的指令都是在该目录下完成的

    c. 将代码文件拷贝到镜像内的工作目录中

    ```dockerfile
    COPY . .
    ```

    第一个. 表示我当前的电脑的目录

    第二个. 表示b步骤中的/app 所在的目录

    d. 安装依赖

    ```dockerfile
    RUN pip install -r requirements.txt
    ```

    RUN表示后面的指令要在镜像中进行

    e. 声明端口号

    ```dockerfile
    EXPOSE 8000
    ```

    表示我的镜像提供服务的端口是哪个，这个EXPOSE只是一个提示作用，不写也不影响。实际使用还是以-p参数为准

    f. 容器启动时自动运行

    ```dockerfile
    CMD ["python3","main.py"]
    ```

    每当容器启动时自动执行这个指令，如，在终端是python3 main.py  就需要分别把他们放在一个数组的字符串中，且中间最好不要有空格

    一个Dockerfile只能有一个CMD

    与之类似的是ENTRYPOINT,他的优先级更高，不易被覆盖

 2. 构建镜像

    ``` shell
    docker build -t docker_test：版本号 .
    ```

    其中，自定义名称是docker_test, 版本号和冒号可以省略不写， 最后的. 表示在宿主机当前目录中构建镜像

    注：在构建镜像的这一步骤中，易出现访问错误（镜像源问题），权限不正确（可加sudo尝试）

    镜像源推荐：

    ```
    {                                                                             
      "registry-mirrors": ["https://hub.uuuadc.top", "https://docker.1panel.live"]
    }
    ```

    另外，pip下载也可能出现错误，推荐在Dockerfile中使用环境变量

    ```dockerfile
    FROM python:3.13-slim
    
    WORKDIR /app
    
    COPY . .
    # 使用国内清华源
    ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
    ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
    
    RUN pip install --upgrade pip && \
        pip install -r requirements.txt
    
    EXPOSE 8000
    
    CMD ["python3", "main.py"]
    
    ```

    如有报错，进行文件的编写，然后进行构建即可

	3. 验证镜像

    我们可以使用**sudo docker run -d -p 8000:8000 docker_test**，来验证镜像是否创建成功

3. 将镜像推送到docker hub
   1. 首先使用**docker login -u wnyngqng** 进行登陆，在弹出的页面中 将验证码输入到所给的连接中,当提示

   Login Succeeded时，我们的登录就成功了

   登陆时注意加速镜像站点的配置和代理配置等的设置

   其次是登陆需要的token需要read&&write的设置选项

   2. 重现构建镜像

      因为构建镜像的时候， 必须要带我们的用户名称，所有现在需要重新构建镜像

      dokcer build -t wnyngqng/docker_test  .

   3. 推送镜像

      docker push wnyngqng/docker_test

      ```
      (.venv) wyq@wyq:~/下载/code/Main$ docker push wnyngqng/docker_test
      Using default tag: latest
      The push refers to repository [docker.io/wnyngqng/docker_test]#仓库地址/命名空间/镜像名称
      fc5d385c5b36: Pushed 
      88a36765208f: Pushed 
      4d6a2e931a27: Pushed 
      1bab0b6d76a5: Pushed 
      127752c2ee4f: Pushed 
      6b34abe788a4: Pushed 
      daf557c4f08e: Pushed 
      latest: digest: sha256:f52980c8206cb8a010237eaee065bbdd52611a42b16227485555e0a5d37a645e size: 1788
      (.venv) wyq@wyq:~/下载/code/Main$ 
      ```

      可以看到推送成功

      在推送成功之后，可以在hub上面搜索我的 **命名空间/镜像名称** 可以看到我的镜像

## docker网络

### 桥接模式

docker网络与宿主机之间是通过桥接模式进行网络连接的，默认ip从172.17.0.2开始

容器可以和容器之间通过ip进行访问，但是容器与宿主机之间的网络不是互通的

#### 创建子网

我们可以使用**docker network create network1** ，创建了子网network1（该子网也属于桥接）,将不同的容器加入子网，子网内的容器可以相互通信。而跨子网不可通信

在创建子网后，我们可以通过容器名字代替ip进行访问而不必使用内部ip，也就是docker内部的DNS会帮我们进行解析

#### 加入子网 

在创建好子网之后，可以在容器之前加上**--network 子网名称**，就能让该容器加入子网

假设有两台容器在同一个子网中，那么我们只需要对一台容器进行端口映射，那么就可以通过浏览器访问该端口映射的容器，然后又通过该容器访问另一个容器

### host模式

docker容器直接共享宿主机的网络，容器直接使用宿主机的ip，无需进行端口映射，容器内的服务直接运行在宿主机的端口上，通过宿主机的ip+port访问容器

#### 利用host模式启动一个容器

sudo docker run -d **--network  host** nginx

该方式没有使用端口映射，我们可以直接localhost:80访问到nginx

#### host模式如何在容器内查看ip

首先进入容器内部 docker exec -it id  /bin/sh

然后安装对应的工具，注：容器内的访问可能过慢，可以使用

```shell
sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list
sed -i 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list
apt update
```

后，继续执行下一步

apt update

apt install iproute2

查看ip

ip addr show

可以看到容器内显示的ip与宿主机的ip一致

### none模式

无网络模式

使用dokcer network list可以查看所有的docker网络

可以使用docker network rm id 删除子网，id由list给出

## docker compose容器编排技术

将不同模块（前端，后端，数据库等）进行编排

他的相关指令放在yaml文件中， 可以理解为将docker run按照一定的格式放在一个文件中

eg：

​	我们启动一个容器

```shell
docker network create network1 #新建一个子网

docker run -d \ #启动容器1
--name my_mongodb \
-e MONGO_INITDB_ROOT_USERNAME=name \
-e MONGO_INITDB_ROOT_PASSWORD=pass \
-v /my/datadir:/data/db \
--network network1 \
mongo

docker run -d \ #启动容器2
--name my_mongodb_express \
-p 8081:8081
-e ME_CONFIG_MONGODB_SERVER=my_mongodb\
-e ME_CONFIG_MONGODB_ADMINUSERNAME=name\
-e ME_CONFIG_MONGODB_ADMINPASSWORD=pass\
--network network1 \
mongo-express
```

那么在yaml编排文件中为

```yaml
services:
	my_mongodb:
		image:mongo
		environment:
			MONGO_INITDB_USERNAME:name
			MONGO_INIRDB_PASSWORD:pass
		volumes:
			- /my/datadir:/data/db
			
	my_mongodb_express:
		image:mongo-express
		port:
			- 8081:8081
		environment:
			ME_CONFIG_MONGODB_SERVER:my_mongodb
			ME_CONFIG_MONGODB_ADMINUSERNAME:name
			ME_CONFIG_MONGODB_ADMINPASSWORD:pass
```

docker会为每一个编排文件自动创建一个子网， 所以这边也没有手动添加创建子网的指令

若我们在上述加上(也就是在最后，第二个容器的后面)

```yaml
depends_on:
	- my_mongodb
```

则表示my_mongodb_express容器依赖my_mongodb容器，则程序会先把mongodb的容器启动起来，再去启动mongo-express

我们只需要将docker指令给ai,让他生成一个等价的docker compose文件就可以了



在使用时，首先创建一个yaml文件

```yaml
services:
  my_mongodb:
    image: mongo:7
    container_name: my_mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: name
      MONGO_INITDB_ROOT_PASSWORD: pass
    volumes:
      - /my/datadir:/data/db
    networks:
      - network1

  my_mongodb_express:
    image: mongo-express:1
    container_name: my_mongodb_express
    restart: unless-stopped
    ports:
      - "8081:8081"
    environment:
      ME_CONFIG_MONGODB_SERVER: my_mongodb
      ME_CONFIG_MONGODB_ADMINUSERNAME: name
      ME_CONFIG_MONGODB_ADMINPASSWORD: pass
    networks:
      - network1
    depends_on:
      - my_mongodb

networks:
  network1:
    name: network1
    driver: bridge

```



然后执行docker compose up -d 即可，同样的-d表示分离启动

```shell
wyq@wyq:~$ sudo docker compose up -d
[+] Running 18/18
 ✔ my_mongodb Pulled                                                                                                            53.4s 
   ✔ 60d98d907669 Pull complete                                                                                                 15.5s 
   ✔ ec080621ab5b Pull complete                                                                                                 15.5s 
   ✔ d931995d7c3b Pull complete                                                                                                 15.6s 
   ✔ 708b21e918f1 Pull complete                                                                                                 18.4s 
   ✔ b400a31ec3bf Pull complete                                                                                                 18.4s 
   ✔ c67e38654598 Pull complete                                                                                                 19.0s 
   ✔ 8100c7c13643 Pull complete                                                                                                 45.2s 
   ✔ fd6cb34e0f73 Pull complete                                                                                                 45.3s 
 ✔ my_mongodb_express Pulled                                                                                                    78.4s 
   ✔ 619be1103602 Pull complete                                                                                                  2.3s 
   ✔ 7e9a007eb24b Pull complete                                                                                                  7.4s 
   ✔ 5189255e31c8 Pull complete                                                                                                 70.8s 
   ✔ 88f4f8a6bc8d Pull complete                                                                                                 70.8s 
   ✔ d8305ae32c95 Pull complete                                                                                                 70.8s 
   ✔ 45b24ec126f9 Pull complete                                                                                                 70.8s 
   ✔ 9f7f59574f7d Pull complete                                                                                                 72.7s 
   ✔ 0bf3571b6cd7 Pull complete                                                                                                 72.7s 
[+] Running 3/3
 ✔ Network network1              Created                                                                                         0.0s 
 ✔ Container my_mongodb          Started                                                                                         0.5s 
 ✔ Container my_mongodb_express  Started    
```

> 我们的yaml文件名称必须为docker-compose.yaml 名称错误会无法识别，进而使用compose up报错
>
> 其次对于已经compose up的指令再次进行compose up也不会启动新的容器，而是无用

当文件名为test.yaml时，直接compose up不行

但可以使用

**compose -f 文件路径/文件名称**，这样的方式也可以

执行docker ps可以看到正在运行的容器，也可以在浏览器进行访问

对于该方式启动的容器，可以使用

**docker compose down** 停止并删除由yaml编排的容器

如果只想停止容器，但是不想删除容器，则可以使用

**docker compose stop**

再次启动容器为，**docker compose start**

docker compose适合个人轻量级的容器进行



对于大型的企业级则需要Kubernetes（k8s）登场
